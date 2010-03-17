from distutils.core import setup
from decimal import Decimal
import os
import sys

sys.path.insert(0, './src')

from version import __version__

setup(
    name = "temare",
    version = str(__version__),
    author = "OSRC Sysint team",
    author_email = "osrc-sysint@elbe.amd.com",
#    package_dir = {"" : "src/" },
    packages         = ['src','t'],
#   package_data     = {
#        'src': ['testsuite.tar', 'language_build_config.yaml'],
#        'slbench.benchmarks': ['benchmarks_config.yaml'],
#    },

    url = "http://osrc/",
    scripts = [ "temare" ],
)

import tarfile

def increment_version():
    return str(Decimal(str(__version__)) + Decimal("0.000001"))

def write_version(version):
    fh =  open('src/version.py', "w")
    fh.write("__version__ = %s\n" % (version,))
    fh.close()

if "sdist" in sys.argv or "bdist" in sys.argv:
    if os.environ.has_key("INCREMENT_VERSION") and \
       os.environ["INCREMENT_VERSION"] == "1":
        __version__ = increment_version()
        write_version(__version__)
