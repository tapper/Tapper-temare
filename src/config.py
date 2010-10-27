#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Limits and paths and other things that might be changing
"""
import os
from socket import gethostname


# Set some path variables to point to temporary locations for debugging
# Please set debug to False on live installs
debug = False

# Artemis data directory
artemisdir = '/data/bancroft/artemis/live'

# Path to the sqlite database
dbpath = '%s/configs/temare/test-schedule.db' % (artemisdir, )

# Amount of memory available on a host
minmem = 1024
maxmem = 98304

# timeout for test suites in second - means the are killed after this time
tstimeout = 86400

# Number of CPU cores available on a host
mincores = 1
maxcores = 64

# KVM guest start script template
kvm =                                                                         \
        '#!/bin/bash\n'                                                       \
        'export PATH=/usr/local/bin:/usr/bin:$PATH\n'                         \
        'kvmexec=$((which qemu-kvm||which qemu-system-x86_64) 2>/dev/null)\n' \
        'if [ -z "$kvmexec" ]; then\n'                                        \
        '   echo "No KVM executable found. Exiting." >/dev/stderr\n'          \
        '   exit 2\n'                                                         \
        'fi\n'                                                                \
        'if [ $(egrep -c "^flags.* svm .*$" /proc/cpuinfo) -ne 0 ]; '         \
        'then\n'                                                              \
        '   modprobe kvm-amd >/dev/null 2>&1\n'                               \
        'elif [ $(egrep -c "^flags.* vmx .*$" /proc/cpuinfo) -ne 0 ]; '       \
        'then\n'                                                              \
        '   modprobe kvm-intel >/dev/null 2>&1\n'                             \
        'else\n'                                                              \
        '   echo "CPUs have no HVM features. Exiting." >/dev/stderr\n'        \
        '   exit 2\n'                                                         \
        'fi\n'                                                                \
        '$kvmexec '                                                           \
        '-name %(runid)03d-%(test)s '                                         \
        '-k de '                                                              \
        '-daemonize '                                                         \
        '-monitor pty '                                                       \
        '-vnc :%(vnc)d '                                                      \
        '-usbdevice tablet '                                                  \
        '-m %(memory)d '                                                      \
        '-smp %(cores)d '                                                     \
        '-hda %(datadir)s/images/%(imgbasename)s '                            \
        '-hdb %(datadir)s/images/%(mntfile)s '                                \
        '-serial file:/tmp/guest%(runid)d.fifo '                              \
        '-net nic,macaddr=%(macaddr)s '                                       \
        '-net tap,ifname=tap%(vnc)d\n'

# Xen SVM file template
svm =                                                                        \
        'import os, os.path, re\n'                                           \
        'from subprocess import Popen, PIPE\n'                               \
        'arch = os.uname()[4]\n'                                             \
        'qemu32 = (os.path.isfile("/usr/lib/xen/bin/qemu-dm")\n'             \
        '          and not os.path.islink("/usr/lib/xen/bin/qemu-dm"))\n'    \
        'qemu64 = (os.path.isfile("/usr/lib64/xen/bin/qemu-dm")\n'           \
        '          and not os.path.islink("/usr/lib64/xen/bin/qemu-dm"))\n'  \
        'if qemu32 and qemu64:\n'                                            \
        '    raise Exception, "qemu-dm exists in both, lib and lib64"\n'     \
        'elif not qemu32 and not qemu64:\n'                                  \
        '    raise Exception, "qemu-dm not found in lib or lib64"\n'         \
        'elif qemu64 and not re.search("64", arch):\n'                       \
        '    raise Exception, "qemu-dm found in lib64, but we are on 32b"\n' \
        'elif qemu64:\n'                                                     \
        '    device_model = "/usr/lib64/xen/bin/qemu-dm"\n'                  \
        'else:\n'                                                            \
        '    device_model = "/usr/lib/xen/bin/qemu-dm"\n'                    \
        'kernel = "/usr/lib/xen/boot/hvmloader"\n'                           \
        'builder = "hvm"\n'                                                  \
        'vif = [ "mac=%(macaddr)s,bridge=xenbr0" ]\n'                        \
        'vnc = 1\n'                                                          \
        'vnclisten = "0.0.0.0"\n'                                            \
        'vncpasswd = ""\n'                                                   \
        'serial = "file:/tmp/guest%(runid)d.fifo"\n'                         \
        'monitor = 1\n'                                                      \
        'usb = 1\n'                                                          \
        'usbdevice = "tablet"\n'                                             \
        'name = "%(runid)03d-%(test)s"\n'                                    \
        'disk = [ "%(format)s:/xen/images/%(imgbasename)s,hda,w",\n'         \
        '         "file:/xen/images/%(mntfile)s,hdb,w" ]\n'                  \
        'boot = "c"\n'                                                       \
        'acpi = 1\n'                                                         \
        'apic = 1\n'                                                         \
        'pae = 1\n'                                                          \
        'timer_mode = 2\n'                                                   \
        'hpet = 0\n'                                                         \
        'shadow_memory = %(shadowmem)d\n'                                    \
        'memory = %(memory)d\n'                                              \
        'vcpus = %(cores)d\n'                                                \
        'hap = %(hap)d\n'

# Designation of the guest image formats as used in the guest configuration
formats = {'raw': 'tap:aio', 'qcow': 'tap:qcow',
        'qcow2': 'tap:qcow2', 'file': 'file'}

# Command to generate svm files on hosts for manual testing
cfgscript = 'echo \'%%s\' >/xen/images/%(runid)03d.%(cfgext)s'

# Command to copy guest image files onto hosts for manual testing
copyscript =                                                                \
        'test -d /xen/images || exit 1; '                                   \
        'if [ -d /mnt/official_testing ]; then '                            \
        '/bin/cp /mnt/official_testing/%s /xen/images/%s >/dev/null 2>&1; ' \
        'else /usr/bin/scp -q -o PasswordAuthentication=no '                \
        'osko:/export/image_files/official_testing/%s /xen/images/%s; fi'

# Harddisk image containing testsuites for manual testing
suiteimage = 'testsuites_raw.img'

# Full filename of the image to use for Dom0
osimage = {0: 'suse/suse_sles10_sp2_32b_smp_raw.tar.gz',
           1: 'suse/suse_sles10_sp2_64b_smp_raw.tar.gz'}

# Artemis repository path
artemisrepo = '%s/repository' % (artemisdir, )

# Directory to put the generated svm files into
svmpath = '%s/configs/xen' % (artemisrepo, )

# Directory to put the generated KVM start scripts into
kvmexecpath = '%s/configs/kvm' % (artemisrepo, )

# NFS path to guest image files
imagepath = 'osko:/export/image_files/official_testing'

# Prefix for guest config file location written into the precondition
nfshost = 'bancroft'

# Path to daily Xen builds
builddir = '%s/packages/xen/builds/%%s/%%s' % (artemisrepo, )

# Architecture portion of the build path (0 = 32-bit, 1 = 64-bit)
buildarchs = {0: 'i686', 1: 'x86_64'}


# Filename pattern for unpatched builds
buildpattern = '^%s\.[0-9]{4}-[0-9]{2}-[0-9]{2}\.[0-9a-f_]+\.%s\.tgz$'
templates = {'redhat' : '''   timeout 2

   title RedHat Testing
   kernel $kernel  console=ttyS0,115200 ks=$ks_file ksdevice=eth0 noapic $ARTEMIS_OPTIONS
   initrd $initrd''',
             'suse'    : '''   timeout 2

   title SUSE Testing
   kernel $kernel  console=ttyS0,115200 install=$install autoyast=$ks_file textmode=1 noapic $ARTEMIS_OPTIONS
   initrd $initrd''',}

if debug == True:
    dbpath = 'test-schedule.db'
    nfshost = gethostname()
    svmpath = 'debug/configs'
    kvmexecpath = 'debug/configs'
    builddir = 'debug/builds/%s/%s'

if os.environ.has_key('HARNESS_ACTIVE'):
    dbpath = 't/test-schedule.db'
    nfshost = gethostname()
    svmpath = '/tmp/'
    kvmexecpath = '/tmp/'
    builddir = 't/misc_files/builds/%s/%s'
