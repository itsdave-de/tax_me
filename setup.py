# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in tax_me/__init__.py
from tax_me import __version__ as version

setup(
	name='tax_me',
	version=version,
	description='Kleiner Helfer für steuerliche Angelegenhieten',
	author='itsdave GmbH',
	author_email='dev@itsdave.de',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
