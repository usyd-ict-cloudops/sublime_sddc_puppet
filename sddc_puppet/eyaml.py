
import os
import sublime
import yaml
import textwrap
from sublime_plugin import TextCommand
from sddc_common.pkcs7 import encrypt
from .utils import YAMLHelper, get_setting
from package_control.deps.asn1crypto import pem, x509, keys


def log(s):
	if sublime.active_window().active_view().settings().get('is_puppet_debug',False):
		print('EYAML: {0}'.format(s))


def der_from_pem_file(filename):
	with open(filename,'rb') as fp:
		return pem.unarmor(fp.read())[2]


def convert_x509_keydata(der_cert):
	'''Convert a DER x509 to DER pkcs1.

	This is to handle the situation that rsa only loads pkcs1
	and the ruby eyaml implementation generates x509 certificates
	for the public key.
	'''
	cert = x509.Certificate.load(der_cert)
	return keys.RSAPublicKey(cert.public_key['public_key'].native).dump()


class EyamlEncryptCommand(YAMLHelper,TextCommand):

	def find_before(self, region, selector):
		for r in reversed(self.view.find_by_selector(selector)):
			if r.end() <= region.begin():
				return r

	def find_after(self, region, selector):
		for r in self.view.find_by_selector(selector):
			if r.begin() >= region.end():
				return r

	def find_in(self, region, selector):
		return [r for r in self.view.find_by_selector(selector) if region.contains(r)]

	def run(self, edit, from_file=False):
		indent_char = ' ' if self.view.settings().get('translate_tabs_to_spaces') else '\t'
		indent_size = self.view.settings().get('tab_size')
		indent_unit = indent_char * indent_size
		pkfn = self.get_file_setting('eyaml_public_key_file')
		keydata = der_from_pem_file(pkfn)
		if get_setting('eyaml_public_key_is_x509',True):
			keydata = convert_x509_keydata(keydata)
		for region in self.view.sel():
			if not self.view.match_selector(region.b,'source.yaml string'):
				log('Cursor({0.b}) not on a string {0!r}'.format(region))
				continue
			data_region = self.view.extract_scope(region.b)
			# if on a key
			if self.view.match_selector(region.b,'entity.name.tag.yaml'):
				key_region = data_region
				str_region = self.find_after(data_region, 'source.yaml string')
				str_region = self.view.extract_scope(str_region.begin())
				if not str_region:
					log('String value does not follow key')
					continue
				if self.view.match_selector(str_region.begin(),'entity.name.tag.yaml'):
					log('value is subkey')
					continue
				next_sep = self.find_after(str_region, 'punctuation.separator')
				if next_sep:
					sep_space = self.view.substr(sublime.Region(str_region.end(),next_sep.begin()))
					if not sep_space.strip():
						log('value is quoted subkey {0!r}'.format(next_sep))
						continue
				if data_region != self.find_before(str_region, 'entity.name.tag.yaml'):
					log('non-string value')
					continue
				sub_region = sublime.Region(data_region.end(),str_region.begin())
				if self.find_in(sub_region, 'invalid'):
					log('invalid characters')
					continue
				puncs = self.find_in(sub_region, 'punctuation.definition')
				metas = self.find_in(sub_region, 'meta.property')
				if not all(self.view.match_selector(r.begin(),'punctuation.definition.anchor') for r in puncs+metas):
					log('non anchor/block-scalar punctuation present')
					continue
				data_region = str_region
			else:
				key_region = self.find_before(data_region, 'entity.name.tag.yaml')
			data = self.view.substr(data_region)
			def run_encrypt(raw_data):
				if raw_data[:10]=='ENC[PKCS7,':
					return
				if from_file:
					if os.path.exists(raw_data) or os.path.exists(raw_data.strip()):
						raw_data = raw_data.strip() if not os.path.exists(raw_data) else raw_data
						if os.path.isfile(raw_data):
							with open(raw_data) as fp:
								raw_data = fp.read()
						else:
							log('Encryption target is not a file')
							return
					else:
						log('Encryption target file does not exist')
						return
				log("Encrypting: {0!r}...{1!r}".format(raw_data[:10],raw_data[-10:]))
				return encrypt(raw_data,keydata=keydata,format='DER')
			# data is block
			if self.view.match_selector(data_region.begin(),'string.unquoted.block.yaml'):
				if from_file:
					log('File encryption value cannot be Block-Scalar')
					continue
				indent = data[:len(data) - len(data.lstrip())]
				btype_region = self.find_before(data_region, 'keyword.control.flow.block-scalar')
				if self.view.match_selector(btype_region.begin(), 'keyword.control.flow.block-scalar.literal'):
					self.view.replace(edit, btype_region, '>')
					edata = run_encrypt(textwrap.dedent(data))
				else:
					# Should not encrypt folded.
					# The implementation is too vague.
					# https://github.com/yaml/YAML2/wiki/Folded-Block-Scalars
					log('Encrypting Folded-Block-Scalars forbidden')
					continue
				edata = textwrap.fill(edata,len(indent)+64,initial_indent=indent,subsequent_indent=indent)+'\n'
			else:
				if self.view.match_selector(data_region.begin(),'string.quoted'):
					edata = run_encrypt(yaml.safe_load(data))
				else:
					edata = run_encrypt(data)
				if from_file:
					indent = indent_unit * (self.view.indentation_level(key_region.begin())+1)
					edata = '>\n'+textwrap.fill(edata,len(indent)+64,initial_indent=indent,subsequent_indent=indent)
			if edata is not None:
				self.view.replace(edit, data_region, edata)
	def is_enabled(self,*args,**kwargs):
		return True
