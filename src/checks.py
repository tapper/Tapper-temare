#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Functions for doing basic sanity checks on input values.
"""
import re
import os.path
import urlparse
from config import minmem, maxmem, mincores, maxcores, \
                   formats, tstimeout, grubtemplates


def chk_arg_count(args, count):
    """Validate the number of given arguments
    """
    if len(args) != count:
        raise ValueError('Wrong number of arguments.')


def chk_bigmem(bigmem):
    """Check and translate input value for bigmem (>4 GB memory)
       @return: 0 if only less than 4 GB possible or available
                1 if more than 4 GB possible or available
    """
    if bigmem in ('yes', 'true', '1'):
        return 1
    elif bigmem in ('no', 'false', '0'):
        return 0
    else:
        raise ValueError(
                'Invalid value for bigmem.\n'
                'Valid values are 0|1, false|true, or yes|no.')


def chk_bitness(bitness):
    """Check and translate input value for bitness
       @return: 0 for 32-bit
                1 for 64-bit
    """
    if bitness == '64':
        return 1
    elif bitness == '32':
        return 0
    else:
        raise ValueError(
                'Invalid value for bitness.\n'
                'Valid values are 32|64.')


def chk_cores(cores):
    """Check and translate input value for the number of CPU cores
       Limits set to 1 and 64 for now
       @return: number of cores as integer
    """
    if re.match('^[1-9][0-9]*$', str(cores)) == None:
        raise ValueError(
                'Invalid value for the number of CPU cores.\n'
                'Only positive integer values are allowed.')
    cores = int(cores)
    if cores < mincores or cores > maxcores:
        raise ValueError(
                'Invalid value for the number of CPU cores.\n'
                'The maximum number is limited to %s.' % (maxcores, ))
    return cores


def chk_grub_template(subjectname, replacements):
    """Check for completeness of the values needed to fill the GRUB template
    """
    subject = subjectname.lower()
    if re.search('sles|opensuse', subject):
        template = grubtemplates['suse']
    elif re.search('redhat|rhel|fedora', subject):
        template = grubtemplates['redhat']
    elif subject.endswith('kvm-upstream'):
        template = grubtemplates['redhat']
    else:
        message = 'No GRUB template defined for subject "%s"'
        raise ValueError(message % (subjectname, ))
    try:
        template % replacements
    except KeyError:
        message = 'Values to fill the GRUB template are incomplete.\n' \
                'Please use the completionadd command to define all\n' \
                'required values (ks_file, kernel, initrd, install)'
        raise ValueError(message)


def chk_hostname(hostname):
    """Check input value for the hostname
       Must match regexp ^[A-Za-z][A-Za-z0-9\-]*$
       Length limited to 63 characters
       @return: hostname as string
    """
    hostname = str(hostname)
    if re.match('^[A-Za-z][A-Za-z0-9\-]*$', hostname) == None:
        raise ValueError('Invalid hostname.')
    if len(hostname) > 63:
        raise ValueError(
                'Invalid hostname.\n'
                'The length is limited to 63 characters.')
    return hostname


def chk_imageformat(imageformat):
    """Check input value for the guest image format
       Valid values are defined as the keys of config.formats
       @return: image format
    """
    imageformats = formats.keys()
    if imageformat not in imageformats:
        raise ValueError(
                'Invalid guest image format.\n'
                'Valid values are %s.' % (', '.join(imageformats), ))
    return imageformat


def chk_imagename(imagename):
    """Check input value for the guest image filename
       Must match regexp ^[A-Za-z][A-Za-z0-9_,+@\-\.=]*$
       Length limited to 255 characters
       @return: image filename as string
    """
    imagename = str(imagename)
    if re.match('^[A-Za-z][A-Za-z0-9_,+@\-\.=/]*$', imagename) == None:
        raise ValueError('Invalid guest image filename.')
    if len(imagename) > 255:
        raise ValueError(
                'Invalid guest image filename.\n'
                'The length is limited to 255 characters.')
    if os.path.normpath(imagename) != imagename:
        raise ValueError('Invalid guest image filename.')
    return imagename


def chk_memory(memory):
    """Check and translate input value for the amount of memory
       Limits set to 1G and 32G for now
       Allows extensions M, MB, G and GB
       @return: amount of memory in MB as integer
    """
    memory = str(memory)
    if re.match('^[0-9]*[\.]?[0-9]+([MG][B]?)?$', memory) == None:
        raise ValueError('Invalid value for memory size.')
    if memory.endswith('B'):
        memory = memory.rstrip('B')
    if memory.endswith('G'):
        memory = int(float(memory.rstrip('G')) * 1024)
    elif memory.endswith('M'):
        memory = int(memory.rstrip('M'))
    else:
        memory = int(memory)
    if memory < minmem or memory > maxmem:
        raise ValueError(
                'Invalid memory size.\n'
                'The size must be between %sM and %sM.' % (minmem, maxmem))
    return memory


def chk_ostype(ostype):
    """Check input value for the operating system type
       Must match regexp ^[A-Za-z][A-Za-z0-9_\-]+$
       Length limited to 32 characters
       @return: operating system type as string
    """
    ostype = str(ostype)
    if re.match('^[A-Za-z][A-Za-z0-9_\-]+$', ostype) == None:
        raise ValueError('Invalid name for an OS type.')
    if len(ostype) > 32:
        raise ValueError(
                'Invalid name for an OS type.\n'
                'The length is limited to 32 characters.')
    return ostype


def chk_priority(priority):
    """Check the input value for the Tapper queue bandwidth
    Must be a positive integer value
    """
    priority = str(priority)
    if not priority.isdigit():
        raise ValueError(
                'Invalid priority value.\n'
                'Only positive integer values are allowed.')
    return int(priority)


def chk_runtime(runtime):
    """Check input value for test suite runtime
       Must be a positive integer value
       @return: timeout as integer
    """
    runtime = str(runtime)
    if not runtime.isdigit():
        raise ValueError(
                'Invalid value for the test suite runtime.\n'
                'Only positive integer values are allowed.')
    runtime = int(runtime)
    if runtime == 0:
        runtime = tstimeout / 3
    return runtime


def chk_smp(smp):
    """Check and translate input value for SMP capability
       @return: 0 for single processor
                1 for multi processor
    """
    if smp in ('yes', 'true', '1'):
        return 1
    elif smp in ('no', 'false', '0'):
        return 0
    else:
        raise ValueError(
                'Invalid value for SMP.\n'
                'Valid values are 0|1, false|true, or yes|no.')


def chk_state(state):
    """Check and translate input value for states
       @return: 0 for disabled
                1 for enabled
    """
    if state in ('enable', '1'):
        return 1
    elif state in ('disable', '0'):
        return 0
    else:
        raise ValueError(
                'Invalid value for state.\n'
                'Valid values are 0|1, disable|enable.')


def chk_subject(subject):
    """Check input value for the test subject name
       Must match regexp ^[A-Za-z][A-Za-z0-9_\-\.]*$
       Length limited to 64 characters
       Must start with xen, autoinstall-xen, or autoinstall-kvm
       Must contain sles, rhel, opensuse, fedora, or kvm-upstream
       if it is an autoinstall subject.
       @return: test subject name as string
    """
    subject = str(subject)
    if re.match('^[A-Za-z][A-Za-z0-9_\-\.]*$', subject) == None:
        raise ValueError('Invalid test subject name.')
    if len(subject) > 64:
        raise ValueError(
                'Invalid test subject name.\n'
                'The length is limited to 64 characters.')
    subjects = ('xen', 'autoinstall-xen', 'autoinstall-kvm')
    if not re.match('^(%s)' % ('|'.join(subjects), ), subject):
        raise ValueError(
                'Invalid test subject name.\n'
                'Possible subjects start with %s.' % (', '.join(subjects), ))
    if subject.startswith('autoinstall'):
        subjects = ('sles', 'rhel', 'fedora', 'opensuse', 'kvm-upstream')
        if not re.search('|'.join(subjects), subject):
            raise ValueError(
                    'Invalid test subject name.\n'
                    'Autoinstall subjects must contain one of the following '
                    'substrings:\n%s' % (', '.join(subjects), ))
    return subject


def chk_testcommand(testcommand):
    """Check input value for the command to start a test program
       Must match regexp ^[A-Za-z][A-Za-z0-9_,+@\-\.=]*$
       Length limited to 255 characters
       @return: test command as string
    """
    testcommand = str(testcommand)
    if re.match('^[A-Za-z0-9_,+@\-\.=/]*$', testcommand) == None:
        raise ValueError(
                'Invalid test command filename "%s".' % (testcommand, ))
    if len(testcommand) > 255:
        raise ValueError(
                'Invalid test command filename "%s".\n'
                'The length is limited to 255 characters.' % (testcommand, ))
    if os.path.normpath(testcommand) != testcommand:
        raise ValueError('Path to test command file is not normalized.')
    return testcommand


def chk_testname(testname):
    """Check input value for the name of the test program
       Must match regexp ^[A-Za-z][A-Za-z0-9_\-]+$
       Length limited to 32 characters
       @return: name of the test program as string
    """
    testname = str(testname)
    if re.match('^[A-Za-z][A-Za-z0-9_\-]+$', testname) == None:
        raise ValueError('Invalid name for a test program.')
    if len(testname) > 32:
        raise ValueError(
                'Invalid name for a test program.\n'
                'The length is limited to 32 characters.')
    return testname


def chk_timeout(timeout):
    """Check input value for test suite runtime
       Must be a positive integer value
       @return: timeout as integer
    """
    timeout = str(timeout)
    if not timeout.isdigit():
        raise ValueError(
                'Invalid value for the test suite timeout.\n'
                'Only positive integer values are allowed.')
    timeout = int(timeout)
    if timeout == 0:
        timeout = tstimeout
    return timeout


def chk_vendor(vendor):
    """Check input value for the vendor name
       Must match regexp ^[A-Za-z][A-Za-z0-9_\-]+$
       Length limited to 32 characters
       @return: name of the vendor as string
    """
    vendor = str(vendor)
    if re.match('^[A-Za-z][A-Za-z0-9_\-]+$', vendor) == None:
        raise ValueError('Invalid name for a vendor.')
    if len(vendor) > 32:
        raise ValueError(
                'Invalid name for a vendor.\n'
                'The length is limited to 32 characters.')
    return vendor


def chk_grubkey(key):
    """Check input value for a GRUB template key
       Valid keys must be keys of the dictionary config.grubvalues
       @return: GRUB template key as string
    """
    key = str(key)
    if key not in grubvalues.keys():
        raise ValueError('Unknown GRUB template key "%s".' % (key, ))
    return key


def chk_abspath(path):
    """Basic validity check of a given path
       Needs to be an absolute path and must not contain any whitespaces
       @return: path as string
    """
    path = str(path).rstrip('/')
    if not path or path != os.path.abspath(path) or re.search('\s', path):
        raise ValueError(
                'Invalid path "%s".\n'
                'Only absolute paths without whitespaces are allowed.' %
                (path, ))
    return path


def chk_url(url):
    """Basic validity check of a given URL
       @return: URL as string
    """
    url = str(url)
    fragments = urlparse.urlparse(url)
    if fragments.scheme not in ('ftp', 'http'):
        raise ValueError(
                'Invalid URL "%s".\n'
                'Only ftp:// or http:// are allowed.' % (url, ))
    try:
        for domain in fragments.netloc.split('.'):
            chk_hostname(domain)
    except ValueError:
        raise ValueError(
                'Invalid URL "%s".\n'
                'The hostname part contains invalid characters.' % (url, ))
    try:
        chk_abspath(fragments.path)
    except ValueError:
        print fragments.path
        raise ValueError(
                'Invalid URL "%s".\n'
                'The path portion is not an absolute path or '
                'contains whitespaces.' % (url, ))
    if fragments.params or fragments.query or fragments.fragment:
        raise ValueError(
                'Invalid URL "%s".\n'
                'The URL must not contain any parameters, queries, or other '
                'supplemental fragments.' % (url, ))
    return url


# GRUB template substitution keys and their input check functions
# This dictionary can't be put into the config module, because it
# would create a circular dependency
grubvalues = {
        'kernel': chk_abspath, 'initrd': chk_abspath,
        'ks_file': chk_url, 'install': chk_url}
