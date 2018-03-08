
import os
import sublime
from sublime_plugin import TextCommand
from sddc_common.pkcs7 import encrypt
from .utils import ContextCommandHelper, get_setting
from package_control.deps.asn1crypto import pem, x509, keys


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


class EyamlEncryptCommand(ContextCommandHelper,TextCommand):
	def run(self, edit):
		pkfn = self.get_file_setting('eyaml_public_key_file')
		keydata = der_from_pem_file(pkfn)
		if get_setting('eyaml_public_key_is_x509',True):
			keydata = convert_x509_keydata(keydata)
		for region in self.view.sel():
			self.view.replace(edit, region, encrypt(self.view.substr(region),keydata=keydata,format='DER'))
