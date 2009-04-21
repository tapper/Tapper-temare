#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Functions for doing basic sanity checks on input values.
"""
import re
from os.path import normpath
from config import minmem, maxmem, mincores, maxcores


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


def chk_imageformat(format):
    """Check input value for the guest image format
       Valid values are raw, qcow, and qcow2
       @return: raw|qcow|qcow2
    """
    if format not in ('raw', 'qcow', 'qcow2'):
        raise ValueError(
                'Invalid guest image format.\n'
                'Valid values are raw, qcow, or qcow2.')
    return format


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
    if normpath(imagename) != imagename:
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
       @return: test subject name as string
    """
    subject = str(subject)
    if not (subject.startswith('xen') or subject.startswith('kvm')):
        raise ValueError('Invalid test subject name.')
    if re.match('^[A-Za-z][A-Za-z0-9_\-\.]*$', subject) == None:
        raise ValueError('Invalid test subject name.')
    if len(subject) > 64:
        raise ValueError(
                'Invalid test subject name.\n'
                'The length is limited to 64 characters.')
    return subject


def chk_testcommand(testcommand):
    """Check input value for the command to start a test program
       Must match regexp ^[A-Za-z][A-Za-z0-9_,+@\-\.=]*$
       Length limited to 255 characters
       @return: test command as string
    """
    testcommand = str(testcommand)
    if re.match('^[A-Za-z0-9_,+@\-\.=/]*$', testcommand) == None:
        raise ValueError('Invalid test command filename.')
    if len(testcommand) > 255:
        raise ValueError(
                'Invalid test command filename.\n'
                'The length is limited to 255 characters.')
    if normpath(testcommand) != testcommand:
        raise ValueError('Invalid test command filename.')
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
