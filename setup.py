from setuptools import setup
from decimal import Decimal
import os
import sys

from temare.version import __version__

setup(
    name             = "temare",
    version          = str(__version__),
    description      = 'Test run generator',
    author           = "AMD OSRC Tapper team",
    author_email     = "tapper@amd64.org",
    packages         = ['temare','t'],
    license          = 'freebsd',
    url              = "http://amd64.org",
    scripts          = [ "scripts/temare" ],
    install_requires = [ 'pysqlite', 'pyyaml'        ],
)

import tarfile

def increment_version():
    return str(Decimal(str(__version__)) + Decimal("0.000001"))

def write_version(version):
    fh =  open('src/version.py', "w")
    fh.write("__version__ = %s\n" % (version,))
    fh.close()

if "sdist" in sys.argv or "bdist" in sys.argv or "bdist_egg" in sys.argv:
    if os.environ.has_key("INCREMENT_VERSION") and \
       os.environ["INCREMENT_VERSION"] == "1":
        __version__ = increment_version()
        write_version(__version__)
