#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Module for taking all steps required to prepare a testrun
"""
try:
    import yaml
except ImportError:
    raise ValueError(
            'You need to have PyYAML installed on your system.\n'
            'Package names are python-yaml on Debian/Ubuntu/SuSE '
            'and PyYAML on Fedora.')
import os
import sys
import re
import threading
import generator
import time
import dbops
from subprocess import Popen, PIPE, STDOUT
from string import Template
from os.path import basename
from checks import chk_hostname, chk_subject
from config import kvm, svm, formats, cfgscript, copyscript,        \
                   osimage, svmpath, nfshost, suiteimage,           \
                   builddir, buildarchs, buildpattern, imagepath,   \
                   tstimeout, kvmexecpath, templates


class BasePreparation(threading.Thread):
    """Base class to prepare a host for manual testing
    """

    def __init__(self, base, host):
        threading.Thread.__init__(self)
        self.base = base
        self.host = host
        self.testrun = None
        self.stage = ''

    def error_handler(self, reason):
        """Print some details about a failing stage and exit thread
        """
        sys.stderr.write(
                'Preparation of host %s failed\n'
                'Failing stage: %s\n'
                'Reason:\n%s\n' % (self.host, self.stage, reason))
        self.base.failed = 1
        sys.exit(1)

    def do_command(self, command):
        """Execute commands through ssh on the host
        """
        process = Popen(['/usr/bin/ssh', '-o PasswordAuthentication=no',
                'root@%s' % self.host, command], stderr=STDOUT, stdout=PIPE)
        retval = process.wait()
        if retval != 0:
            output = process.communicate()[0]
            if output in (None, ''):
                output = 'Exited with error code %d' % (retval, )
            self.error_handler(output)


class XenHostPreparation(BasePreparation):
    """Class to prepare a Xen host for manual testing

    This class has to be run as a thread to allow the loading of
    different hosts at the same time. As soon as the thread is
    started it performs following actions:
     * Checks the status of xend on the specified host
     * Checks for other guests that might still be running
     * Wipes out old guest configuration files and images from the host
     * Generates new guest configuration files on the host
     * Copies guest images either through NFS or scp onto the host
     * Starts all guests
     * Marks tests as done in the database

    Arguments:
        base    --  Reference to the calling class (used for error reporting)
        host    --  Name of the host to start the test run on
    """

    def __init__(self, base, host):
        BasePreparation.__init__(self, base, host)

    def run(self):
        """Take all steps required to start all guests on the host
        """
        self.stage = 'Generating tests'
        try:
            self.host = chk_hostname(self.host)
            self.testrun = generator.TestRunGenerator(self.host)
        except ValueError, err:
            self.error_handler(err[0])
        for test in self.testrun.tests:
            test['mntfile'] = '%(runid)03d-%(test)s.img' % test
            test['format'] = formats[test['format']]
            test['imgbasename'] = basename(test['image'])
            test['cfgext'] = 'svm'
        self.stage = 'Check xend status'
        self.do_command('/usr/sbin/xend status')
        self.stage = 'Check for running guests'
        self.do_command('test `/usr/sbin/xm list |wc -l` -eq 2')
        self.stage = 'Cleanup old guest configs, images, and logs'
        self.do_command('/bin/rm -f /xen/images/*.{svm,img} /tmp/*.fifo')
        self.stage = 'Generate guest configuration files'
        for test in self.testrun.tests:
            self.do_command((cfgscript % test) % ((svm % test), ))
        self.stage = 'Copying testsuite image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % ((suiteimage, test['mntfile']) * 2))
        self.stage = 'Copying guest image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % tuple([test['image']] * 4))
        self.stage = 'Starting guests'
        for test in self.testrun.tests:
            svmfile = '%(runid)03d.svm' % test
            self.do_command('/usr/sbin/xm create /xen/images/%s' % (svmfile, ))
        numguests = len(self.testrun.tests)
        self.testrun.do_finalize()
        sys.stdout.write(
                '%s done. Number of guests started: %d\n' %
                (self.host, numguests, ))


class KvmHostPreparation(BasePreparation):
    """Class to prepare a KVM host for manual testing

    This class has to be run as a thread to allow the loading of
    different hosts at the same time. As soon as the thread is
    started it performs following actions:
     * Checks if kernel modules are loaded
     * Checks for other guests that might still be running
     * Wipes out old guest images from the host
     * Copies guest images either through NFS or scp onto the host
     * Starts all guests
     * Marks tests as done in the database

    Arguments:
        base    --  Reference to the calling class (used for error reporting)
        host    --  Name of the host to start the test run on
    """

    def __init__(self, base, host):
        BasePreparation.__init__(self, base, host)

    def run(self):
        """Take all steps required to start all guests on the host
        """
        self.stage = 'Generating tests'
        try:
            self.host = chk_hostname(self.host)
            self.testrun = generator.TestRunGenerator(self.host)
        except ValueError, err:
            self.error_handler(err[0])
        for test in self.testrun.tests:
            test['mntfile'] = '%(runid)03d-%(test)s.img' % test
            test['imgbasename'] = basename(test['image'])
            test['datadir'] = '/xen'
            test['cfgext'] = 'sh'
        self.stage = 'Check for kernel modules'
        self.do_command('/sbin/modprobe kvm kvm-amd kvm-intel && '
                '/sbin/lsmod | /bin/grep -q "^kvm "')
        self.stage = 'Check for running guests'
        self.do_command(
                'test `ps -C qemu-kvm -C qemu-system-x86_64 | wc -l` -eq 1')
        self.stage = 'Cleanup old guest configs, images, and logs'
        self.do_command('/bin/rm -f /xen/images/*.{sh,img} /tmp/*.fifo')
        self.stage = 'Generate guest start scripts'
        for test in self.testrun.tests:
            test['startscript'] = '/xen/images/%(runid)03d.%(cfgext)s' % test
            self.do_command((cfgscript % test) % ((kvm % test), ))
            self.do_command('chmod 755 %s' % (test['startscript'], ))
        self.stage = 'Copying testsuite image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % ((suiteimage, test['mntfile']) * 2))
        self.stage = 'Copying guest image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % tuple([test['image']] * 4))
            self.do_command(
                    'qemu-img convert -O raw /xen/images/%s /xen/images/%s.tmp'
                    % tuple([test['image']] * 2))
            self.do_command(
                    'mv -f /xen/images/%s.tmp /xen/images/%s'
                    % tuple([test['image']] * 2))
        self.stage = 'Starting guests'
        for test in self.testrun.tests:
            self.do_command(test['startscript'])
        numguests = len(self.testrun.tests)
        self.testrun.do_finalize()
        sys.stdout.write(
                '%s done. Number of guests started: %d\n' %
                (self.host, numguests, ))


class SubjectPreparation():
    """Class to generate preconditions for an Artemis test run

    Finds possible tests for the specified host, writes guest configuration
    files to a specific directory and writes a YAML precondition string
    to STDOUT.

    Arguments:
        host    --  Name of the host to start the test run on
        subject  -- Specific test subject to be chosen (optional)
        bitness  -- Bitness of the specific test subject
                    (only required if test subject is specified)
    """

    def __init__(self, host, subject=False, bitness=False):
        self.build = None
        self.builddir = None
        self.guestconfigs = {}
        self.host = chk_hostname(host)
        self.subject = subject
        self.testrun = generator.TestRunGenerator(
                self.host, True, subject, bitness)
        self.dry_mode = 0

    def get_latest_build(self):
        """Find latest build of a test subject

        Sets following attributes:
            SubjectPreparation.build    --  Filename of the build
            SubjectPreparation.builddir --  Directory containing the build
        """
        builds = []
        arch = buildarchs[self.testrun.resources['bitness']]
        version = chk_subject(self.testrun.subject['name'])
        pattern = buildpattern % (version.replace('.', '\.'), arch)
        self.builddir = builddir % (arch, version)
        try:
            for build in os.listdir(self.builddir):
                if re.match(pattern, build):
                    builds.append(build)
        except OSError:
            message = 'Build directory "%s" does not exist.'
            raise ValueError(message % (self.builddir, ))
        if len(builds) < 1:
            message = 'No builds available for %s on %s.\nBuilddir is %s'
            raise ValueError(message % (version, arch, self.builddir))
        builds.sort()
        self.build = builds.pop()

    def __write_config(self, filename, path, test, template):
        """Write a guest config file or start script to the specified location

        Expects:
            filename - Name of the file to be written
            path     - Location to store the file into
            test     - Dictionary of a single guest test
            template - Template of the files content
        """
        if self.dry_mode == 1:
            return
        filepath = '%s/%s' % (path, filename)
        cfgfile = None
        try:
            cfgfile = open(filepath, 'w')
            cfgfile.write(template % test)
        except:
            raise ValueError('Failed to write guest config files.')
        finally:
            if type(cfgfile) == file:
                cfgfile.close()
        if filepath.endswith('.sh'):
            os.chmod(filepath, 0o755)

    def gen_guest_configs(self):
        """Write guest configuration files

        Guest configuration files get written into a directory which is
        specified through config.svmpath or config.kvmexecpath.
        Naming convention is

            [0-9]{3}-${hostname}-${date +%s}.(svm|sh)

        Config files from prior runs will be overwritten.
        """
        timestamp = time.mktime(time.gmtime())
        for test in self.testrun.tests:
            prefix = '%03d-%s-%ld' % (test['runid'], self.host, timestamp)
            test['mntfile'] = '%s.img' % (prefix, )
            test['format'] = formats[test['format']]
            test['imgbasename'] = basename(test['image'])
            if self.testrun.subject['name'].startswith('xen'):
                test['svmfile'] = '%s.svm' % (prefix, )
                self.__write_config(test['svmfile'], svmpath, test, svm)
            elif self.testrun.subject['name'].startswith('kvm') \
                    or self.testrun.subject['name'].startswith('autoinstall'):
                test['datadir'] = '/kvm'
                test['kvmexec'] = '%s.sh' % (prefix, )
                self.__write_config(test['kvmexec'], kvmexecpath, test, kvm)
            else:
                raise ValueError('Invalid test subject.')

    def __write_subjectinfo(self, filename):
        """Write a YAML dump of the test subject description to a file

        Expects:
            filename - Path of the file to be written to
        """
        data = {'subject': self.testrun.subject['name']}
        infofile = None
        try:
            infofile = open(filename, 'w')
            infofile.write(yaml.safe_dump(data, default_flow_style=False))
        except:
            raise ValueError('Failed to write test subject description file.')
        finally:
            if type(infofile) == file:
                infofile.close()

    def gen_precondition(self):
        """Prepare a test run and generate a precondition YAML string

        Just calls the appropriate method for the test subject which was
        determined by calling the test run generator.
        """
        precondition = ""
        if self.testrun.subject['name'].startswith('xen'):
            precondition = (self.gen_precondition_xen())
        elif self.testrun.subject['name'].startswith('kvm'):
            precondition = (self.gen_precondition_kvm())
        elif self.testrun.subject['name'].startswith('autoinstall'):
            precondition = self.gen_precondition_autoinstall()
        else:
            raise ValueError('Invalid test subject.')
        self.write_precondition(precondition)

    def gen_xen_host(self, options):
        """ Generate host part of a Xen precondition"""

        return {
            'root': {
                    'precondition_type':    'image',
                    'mount':                '/',
                    'partition':            '/dev/sda2',
                    'arch':                 options['arch'],
                    'image':                options['osimagefile']},
                'testprogram': {
                    'execname':             options['testprogram'],
                    'timeout_testprogram':  300,
                    'runtime':              50},
                'preconditions': [
                    {'precondition_type':   'package',
                     'filename':            self.builddir + '/' + self.build},
                    {'precondition_type':   'package',
                     'filename':            options['installpkg']},
                    {'precondition_type':   'exec',
                     'filename':            '/bin/xen_install.sh',
                     'options':             [ self.subject ] },
                    {'precondition_type':   'package',
                     'filename':            'artemisutils/sles10/netxtreme2.tgz'},
                    {'precondition_type':   'package',
                     'filename':            'artemisutils/sles10/linux-xen.tgz'},
                    {'precondition_type':   'exec',
                     'filename':            '/bin/build_netxtreme2'}]
                }

    def gen_xen_guest_options(self, test):
        guest_options                       = {}
        guest_options['subject']            = self.testrun.subject['name']
        guest_options['imagefile']          = '%s/%s' % (imagepath, test['image'])
        guest_options['mountfile']          = '/xen/images/%s' % (test['mntfile'], )
        guest_options['guest_start_source'] = '%s:%s/%s' % (nfshost, svmpath, test['svmfile'])
        guest_options['guest_start_dest']   = '%s/%s' % ('/xen/images/', test['svmfile'])
        guest_options['used_timeout']       = tstimeout
        guest_options['used_runtime']       = tstimeout / 3
        guest_options['testcommand']        = test['testcommand']
        guest_options['ostype']             = test['ostype']

        if test['timeout']:
            guest_options['used_timeout'] = test['timeout']
        if test['runtime']:
            guest_options['used_runtime'] = test['runtime']

        if test['ostype'].lower().startswith('windows'):
            guest_options['arch'] = 'windows'
        elif test['bitness'] == 1:
            guest_options['arch'] = 'linux64'
        else:
            guest_options['arch'] = 'linux32'
        return guest_options

    def gen_guest_precond(self, guest_options):
        path = ''
        if guest_options['subject'].startswith('kvm') or guest_options['subject'].startswith('autoinstall'):
            path = '/kvm/images/'
        elif guest_options['subject'].startswith('xen'):
            path = '/xen/images/'


        retval = {
                'root': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 guest_options['imagefile'],
                    'mountfile':            guest_options['mountfile'],
                    'mounttype':            'raw',
                    'arch'     :            guest_options['arch'],
                    'dest':                 path,
                    },
                'config': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 guest_options['guest_start_source'], # source for svm or kvm_start_script
                    'dest':                 path,
                    },
                'testprogram': {
                    'execname':             guest_options['testcommand'],
                    'timeout_testprogram':  guest_options['used_timeout'],
                    'runtime':              guest_options['used_runtime'],
                    }
                }
        if guest_options['ostype'].lower().startswith('windows'):
            retval['root']['mounttype']      = 'windows'
            retval['root']['mountpartition'] = 'p1'



        if (guest_options['subject'].lower().find('kvm') != -1):
            retval['config']['exec'] = guest_options['guest_start_dest']
        elif (guest_options['subject'].lower().find('xen') != -1):
            retval['config']['svm']  = guest_options['guest_start_dest']
        return retval

    def gen_precondition_autoinstall(self):
        """Prepare a testrun using autoinstall tools like kickstart or autoyast.

        Generate guest configurations, write a precondition string to STDOUT,
        and finally mark the guest tests as done in the database.
        """
        self.gen_guest_configs()

        options = {}
        subject = self.testrun.subject['name'].lower()
        if re.search('sles|opensuse', subject):
            options['template'] = Template(templates['suse'])
        elif re.search('redhat|rhel|fedora', subject):
            options['template'] = Template(templates['redhat'])

        # FIXME:
        # * String module deprecated, use built-in templating
        # * Stubborn data structure returned from dbops.Completions().get()
        substitutions = {}
        compops = dbops.Completions()
        subject = self.testrun.subject['name']
        bitness = ("32", "64")[self.testrun.subject['bitness']]
        for line in compops.get((subject, bitness)):
            substitutions[line['key']] = line['value']
        options['template'] = options['template'].safe_substitute(substitutions)
        # FIXME end

        options['testprogram'] = '/opt/artemis/bin/metainfo'

        precondition = {
            'precondition_type':   'virt',
            'name':                'automatically generated KVM test'}
        precondition['host'] = {
                'root': {
                    'grub_text'         : options['template'],
                    'name'              : self.testrun.subject['name'],
                    'precondition_type' : 'autoinstall',
                    'timeout'           : 10000,
                    },
                'testprogram': {
                    'execname':             options['testprogram'],
                    'timeout_testprogram':  300,
                    'runtime':              50,
                    },
                }

        precondition['guests'] = []
        for test in self.testrun.tests:
            guest_options                       = {}
            guest_options['subject']            = self.testrun.subject['name']
            guest_options['imagefile']          = '%s/%s' % (imagepath, test['image'])
            guest_options['mountfile']          = '/kvm/images/%s' % (test['mntfile'], )
            guest_options['guest_start_source'] = '%s:%s/%s' % (nfshost, kvmexecpath, test['kvmexec'])
            guest_options['guest_start_dest']   = '/kvm/images/%s' % (test['kvmexec'], )
            guest_options['used_timeout']       = tstimeout
            guest_options['used_runtime']       = tstimeout / 3
            guest_options['testcommand']        = test['testcommand']
            guest_options['ostype']             = test['ostype']

            if test['timeout']:
                guest_options['used_timeout'] = test['timeout']
            if test['runtime']:
                guest_options['used_runtime'] = test['runtime']

            if test['ostype'].lower().startswith('windows'):
                guest_options['arch'] = 'windows'
            elif test['bitness'] == 1:
                guest_options['arch'] = 'linux64'
            else:
                guest_options['arch'] = 'linux32'

            guest = self.gen_guest_precond(guest_options)
            precondition['guests'].append(guest)
        return precondition

    def gen_precondition_xen(self):
        """Prepare a Xen test run and generate a precondition YAML string

        Find latest build of the test subject, generate guest
        configurations, write a precondition string to STDOUT, and finally
        mark the guest tests as done in the database.
        """
        self.get_latest_build()
        self.gen_guest_configs()
        options                = {}
        options['arch']        = ('linux32', 'linux64')[self.testrun.subject['bitness']]
        options['osimagefile'] = osimage[self.testrun.subject['bitness']]
        options['testprogram'] = '/opt/artemis/bin/metainfo'
        options['installpkg']  = 'artemisutils/sles10/xen_installer_suse.tar.gz'

        precondition           = {
            'precondition_type': 'virt',
            'name'             : 'automatically generated Xen test'}
        precondition['host']   = self.gen_xen_host(options)
        precondition['guests'] = []

        for test in self.testrun.tests:
            guest_options = self.gen_xen_guest_options(test)
            guest = self.gen_guest_precond(guest_options)
            precondition['guests'].append(guest)
        return precondition

    def gen_precondition_kvm(self):
        """Prepare a KVM test run and generate a precondition YAML string

        Generate guest configurations, write a precondition string to STDOUT,
        and finally mark the guest tests as done in the database.
        """
        self.gen_guest_configs()
        precondition = {
            'precondition_type':   'virt',
            'name':                'automatically generated KVM test'}
        precondition['host'] = {
            'root': {
                'grub_text': '''timeout 2

title Fedora 14 with KVM
kernel /tftpboot/stable/fedora/14/x86_64/vmlinuz console=ttyS0,115200 ks=http://bancroft/autoinstall/stable/fedora/14/x86_64/kvm-upstream.ks ksdevice=link $ARTEMIS_OPTIONS
initrd /tftpboot/stable/fedora/14/x86_64/initrd.img
''',
                'name': 'Fedora_14',
                'precondition_type': 'autoinstall',
                'timeout': '10000',
            },
            'testprogram_list': [
                {
                    'execname':             '/opt/artemis/bin/py_kvm_unit',
                    'runtime':              1200,
                    'timeout_testprogram':  1800,
                },
                {
                    'execname':             '/opt/artemis/bin/metainfo',
                    'timeout_testprogram':  300,
                    'runtime':              50,
                },
            ]
        }
        precondition['guests'] = []
        for test in self.testrun.tests:
            guest_options                       = {}
            guest_options['subject']            = self.testrun.subject['name']
            guest_options['imagefile']          = '%s/%s' % (imagepath, test['image'])
            guest_options['mountfile']          = '/kvm/images/%s' % (test['mntfile'], )
            guest_options['guest_start_source'] = '%s:%s/%s' % (nfshost, kvmexecpath, test['kvmexec'])
            guest_options['guest_start_dest']   = '/kvm/images/%s' % (test['kvmexec'], )
            guest_options['used_timeout']       = tstimeout
            guest_options['used_runtime']       = tstimeout / 3
            guest_options['testcommand']        = test['testcommand']
            guest_options['ostype']             = test['ostype']

            if test['timeout']:
                guest_options['used_timeout'] = test['timeout']
            if test['runtime']:
                guest_options['used_runtime'] = test['runtime']

            if test['timeout']:
                guest_options['used_timeout'] = test['timeout']
            if test['runtime']:
                guest_options['used_runtime'] = test['runtime']

            if test['ostype'].lower().startswith('windows'):
                guest_options['arch'] = 'windows'
            elif test['bitness'] == 1:
                guest_options['arch'] = 'linux64'
            else:
                guest_options['arch'] = 'linux32'

            guest = self.gen_guest_precond(guest_options)
            precondition['guests'].append(guest)
        return precondition

    def write_precondition(self, precondition):
        """Write a given precondition and subjectinfo

        Precondition is always written to STDOUT.
        Subjectinfo is only written when working for ARTEMIS - i.e. when
        $ARTEMIS_TEMARE is set. It is written to an associated file.
        """
        sys.stdout.write(yaml.safe_dump(precondition,
                default_flow_style=False, width=500))
        if os.environ.has_key('ARTEMIS_TEMARE'):
            self.__write_subjectinfo(os.environ['ARTEMIS_TEMARE'])
        self.testrun.do_finalize()


if __name__ == '__main__':
    pass
