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
from subprocess import Popen, PIPE, STDOUT
from os.path import basename
from checks import chk_hostname, chk_subject
from config import kvm, svm, formats, cfgscript, copyscript,        \
                   osimage, xencfgstore, nfshost, suiteimage,       \
                   builddir, buildarchs, buildpattern, imagepath,   \
                   kvmcfgstore, grubtemplates, virtdirman


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
        base -- Reference to the calling class (used for error reporting)
        host -- Name of the host to start the test run on
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
            test['cfgfile'] = '%(datadir)s/%(runid)03d.%(cfgext)s' % test
        self.stage = 'Check xend status'
        self.do_command('/usr/sbin/xend status')
        self.stage = 'Check for running guests'
        self.do_command('test `/usr/sbin/xm list |wc -l` -eq 2')
        self.stage = 'Cleanup old guest configs, images, and logs'
        self.do_command(
                '/bin/rm -f %s/*.{svm,img} /tmp/*.fifo' % (virtdirman, ))
        self.stage = 'Generate guest configuration files'
        for test in self.testrun.tests:
            self.do_command((cfgscript % test) % ((svm % test), ))
        self.stage = 'Copying testsuite image files'
        for test in self.testrun.tests:
            cpscript = copyscript % test
            self.do_command(cpscript % ((suiteimage, test['mntfile']) * 2))
        self.stage = 'Copying guest image files'
        for test in self.testrun.tests:
            cpscript = copyscript % test
            self.do_command(cpscript % tuple([test['image']] * 4))
        self.stage = 'Starting guests'
        for test in self.testrun.tests:
            self.do_command('/usr/sbin/xm create %(cfgfile)s' % test)
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
        base -- Reference to the calling class (used for error reporting)
        host -- Name of the host to start the test run on
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
            test['cfgext'] = 'sh'
            test['cfgfile'] = '%(datadir)s/%(runid)03d.%(cfgext)s' % test
        self.stage = 'Check for kernel modules'
        self.do_command('/sbin/modprobe kvm kvm-amd kvm-intel && '
                '/sbin/lsmod | /bin/grep -q "^kvm "')
        self.stage = 'Check for running guests'
        self.do_command(
                'test `ps -C qemu-kvm -C qemu-system-x86_64 | wc -l` -eq 1')
        self.stage = 'Cleanup old guest configs, images, and logs'
        self.do_command(
                '/bin/rm -f %s/*.{sh,img} /tmp/*.fifo' % (virtdirman, ))
        self.stage = 'Generate guest start scripts'
        for test in self.testrun.tests:
            self.do_command((cfgscript % test) % ((kvm % test), ))
            self.do_command('chmod 755 %s' % (test['cfgfile'], ))
        self.stage = 'Copying testsuite image files'
        for test in self.testrun.tests:
            cpscript = copyscript % test
            self.do_command(cpscript % ((suiteimage, test['mntfile']) * 2))
        self.stage = 'Copying guest image files'
        for test in self.testrun.tests:
            cpscript = copyscript % test
            self.do_command(cpscript % tuple([test['image']] * 4))
            self.do_command(
                    'qemu-img convert -O raw %(datadir)s/%(image)s{,.tmp}'
                    % test)
            self.do_command('mv -f %(datadir)s/%(image)s{.tmp,}' % test)
        self.stage = 'Starting guests'
        for test in self.testrun.tests:
            self.do_command(test['cfgfile'])
        numguests = len(self.testrun.tests)
        self.testrun.do_finalize()
        sys.stdout.write(
                '%s done. Number of guests started: %d\n' %
                (self.host, numguests, ))


class SubjectPreparation():
    """
    Class to generate Tapper virt preconditions

    Finds possible tests for the specified host, writes guest configuration
    files to a specific directory, and finally writes a data structure
    in YAML format to STDOUT.
    """

    def __init__(self, host, subject=False, bitness=False):
        """
        @param host   : Name of the test machine
        @type  host   : str
        @param subject: Name of the test subject (optional)
        @type  subject: str
        @param bitness: Bitness of the test subject (optional)
        @type  bitness: int
        """
        self.host = chk_hostname(host)
        self.testrun = generator.TestRunGenerator(
                self.host, True, subject, bitness)
        self.dry_mode = 0

    def get_latest_build(self):
        """
        Find latest build of a test subject

        @return: Path to the build package on the Tapper server
        @rtype : str
        """
        builds = []
        arch = buildarchs[self.testrun.resources['bitness']]
        version = chk_subject(self.testrun.subject['name'])
        pattern = buildpattern % (version.replace('.', '\.'), arch)
        subjectdir = builddir % (arch, version)
        try:
            for build in os.listdir(subjectdir):
                if re.match(pattern, build):
                    builds.append(build)
        except OSError:
            message = 'Build directory "%s" does not exist.'
            raise ValueError(message % (subjectdir, ))
        if len(builds) < 1:
            message = 'No builds available for %s on %s.\nBuilddir is %s'
            raise ValueError(message % (version, arch, subjectdir))
        builds.sort()
        return os.path.join(subjectdir, builds.pop())

    def __write_guest_configfile(self, filename, content):
        """
        Write a guest configuration file to the specified location

        @param filename: Path of the guest config filename
        @type  filename: str
        @param content : Content of the file
        @type  content : str
        """
        if self.dry_mode == 1:
            return
        try:
            cfgfile = open(filename, 'w')
            cfgfile.write(content)
            cfgfile.close()
        except IOError:
            raise ValueError('Failed to write guest config files.')
        if filename.endswith('.sh'):
            os.chmod(filename, 0755)

    def __gen_precondition_guest(self, test):
        """
        Generate the Tapper precondition for a single guest

        @return: Guest precondition
        @rtype : dict
        """
        config = {
            'precondition_type': 'copyfile',
            'protocol':          'nfs',
            'name':              '%s:%s' % (nfshost, test['cfgfilesrc']),
            test['cfgtype']:     '%(datadir)s/%(cfgfile)s' % test,
            'dest':              test['datadir'],
        }
        testprogram = {
            'execname':            test['testcommand'],
            'timeout_testprogram': test['timeout'],
            'runtime':             test['runtime'],
        }
        root = {
            'precondition_type': 'copyfile',
            'protocol':          'nfs',
            'name':              '%s/%s' % (imagepath, test['image']),
            'mountfile':         '%(datadir)s/%(mntfile)s' % test,
            'mounttype':         'raw',
            'dest':              test['datadir'],
        }
        parselogs = {
            'execname':            '/opt/tapper/bin/py_parselog',
            'timeout_testprogram': 200,
            'runtime':             50,
        }
        osvwtest = {
            'execname':            '/data/tapper/autoreport/xen-osvw.sh',
            'chdir':               'AUTO',
            'timeout_testprogram': 200,
            'runtime':             120,
        }
        testprogramlist = [testprogram, parselogs]
        subject = self.testrun.subject['name'].lower()
        if re.search('osvw', subject):
            testprogramlist.append(osvwtest)
        if test['ostype'].lower().startswith('windows'):
            root['arch'] = 'windows'
            root['mounttype'] = 'windows'
            root['mountpartition'] = 'p1'
            testprogramlist = [testprogram]
        elif test['bitness'] == 1:
            root['arch'] = 'linux64'
        else:
            root['arch'] = 'linux32'
        precondition = {
            'root':        root,
            'config':      config,
            'testprogram_list': testprogramlist,
        }
        return precondition

    def gen_guest_configs(self):
        """
        Generate guest configuration files and preconditions for all guests

        Guest configuration files get written into a directory which is
        specified through config.xencfgstore or config.kvmcfgstore.
        Naming convention is

            [0-9]{3}-${hostname}-${date +%s}.(svm|sh)

        The dictionaries for each guest, as returned from Generator.tests
        and stored in as attribute self.testrun.tests, get extended with
        the following keys:

            mntfile     -- Name of the test suite image       (string)
            format      -- Format of the guest image file     (string)
            imgbasename -- Basename of the guest image        (string)
            cfgfile     -- Basename of the guest config file  (string)
            cfgtype     -- Type of the guest config file      (exec|svm)
            cfgfilesrc  -- Location of the guest config file  (string)
                           on the Tapper server

        Finally, the precondition for each guest is generated.

        @return: Guest preconditions
        @rtype : list
        """
        guests = []
        timestamp = time.mktime(time.gmtime())
        subject = self.testrun.subject['name']
        for test in self.testrun.tests:
            prefix = '%03d-%s-%ld' % (test['runid'], self.host, timestamp)
            test['mntfile'] = '%s.img' % (prefix, )
            test['format'] = formats[test['format']]
            test['imgbasename'] = basename(test['image'])
            if re.search('^xen|autoinstall-xen', subject):
                test['cfgfile'] = '%s.svm' % (prefix, )
                test['cfgfilesrc'] = '%s/%s' % (xencfgstore, test['cfgfile'])
                test['cfgtype'] = 'svm'
                configfile = svm % test
            elif re.search('^autoinstall-kvm', subject):
                test['cfgfile'] = '%s.sh' % (prefix, )
                test['cfgfilesrc'] = '%s/%s' % (kvmcfgstore, test['cfgfile'])
                test['cfgtype'] = 'exec'
                configfile = kvm % test
            else:
                raise ValueError('Invalid test subject "%s".' % (subject, ))
            self.__write_guest_configfile(test['cfgfilesrc'], configfile)
            guests.append(self.__gen_precondition_guest(test))
        return guests

    def gen_precondition_autoinstall(self):
        """
        Generate an Tapper autoinstall precondition

        @return: Tapper autoinstall precondition
        @rtype : dict
        """
        guests = self.gen_guest_configs()
        subject = self.testrun.subject['name'].lower()
        if re.search('sles|opensuse', subject):
            grubtext = grubtemplates['suse']
        elif re.search('redhat|rhel|fedora', subject):
            grubtext = grubtemplates['redhat']
        elif subject.endswith('kvm-upstream'):
            grubtext = grubtemplates['redhat']
        else:
            message = 'No GRUB template defined for subject "%s"'
            raise ValueError(message % (self.testrun.subject['name'], ))
        grubtext = grubtext % self.testrun.subject['completion']
        metainfo = {
            'execname':            '/opt/tapper/bin/metainfo',
            'timeout_testprogram': 300,
            'runtime':             50,
        }
        kvmunit = {
            'execname':            '/opt/tapper/bin/py_kvm_unit',
            'runtime':             1200,
            'timeout_testprogram': 1800,
        }
        xen_core_pair = {
            'execname':            '/data/tapper/autoreport/xen-core-pair-check.sh',
            'timeout_testprogram': 200,
            'runtime':             50,
        }

        testprogramlist = [metainfo, ]
        if re.search('xen', subject):
            name = 'automatically generated Xen test'
            testprogramlist = [metainfo, xen_core_pair,]
        else:
            name = 'automatically generated KVM test'
            if subject.endswith('kvm-upstream'):
                testprogramlist = [metainfo, kvmunit, ]
        root = {
            'precondition_type' : 'autoinstall',
            'name'              : self.testrun.subject['name'],
            'grub_text'         : grubtext,
            'timeout'           : 10000,
        }
        host = {
            'root':             root,
            'testprogram_list': testprogramlist,
        }
        precondition = {
            'precondition_type': 'virt',
            'name':              name,
            'host' :             host,
            'guests':            guests,
        }
        return precondition

    def gen_precondition_xen(self):
        """
        Generate an Tapper Xen precondition

        @return: Tapper autoinstall precondition
        @rtype : dict
        """
        xenbuild = self.get_latest_build()
        guests = self.gen_guest_configs()
        xenpkg = {
            'precondition_type': 'package',
            'filename':          xenbuild,
        }
        dom0pkg = {
            'precondition_type': 'package',
            'filename':          'tapperutils/sles10/linux-xen.tgz',
        }
        instpkg = {
            'precondition_type': 'package',
            'filename': 'tapperutils/sles10/xen_installer_suse.tar.gz',
        }
        inst = {
            'precondition_type': 'exec',
            'filename':          '/bin/xen_install.sh',
            'options':           [self.testrun.subject['name'], ],
        }
        drvpkg = {
            'precondition_type': 'package',
            'filename':          'tapperutils/sles10/netxtreme2.tgz',
        }
        drvinst = {
            'precondition_type': 'exec',
            'filename':          '/bin/build_netxtreme2',
        }
        metainfo = {
            'execname':            '/opt/tapper/bin/metainfo',
            'timeout_testprogram': 300,
            'runtime':             50,
        }
        xen_core_pair = {
            'execname':            '/data/tapper/autoreport/xen-core-pair-check.sh',
            'timeout_testprogram': 200,
            'runtime':             50,
        }
        preconditions = [xenpkg, dom0pkg, instpkg, inst, drvpkg, drvinst]
        testprogramlist = [metainfo, xen_core_pair,]
        root = {
            'precondition_type': 'image',
            'mount':             '/',
            'partition':         '/dev/sda2',
        }
        if self.testrun.subject['bitness'] == 1:
            root['arch'] = 'linux64'
            root['image'] = osimage[1]
        else:
            root['arch'] = 'linux32'
            root['image'] = osimage[0]
        host = {
            'root'         : root,
            'testprogram_list'  : testprogramlist,
            'preconditions': preconditions,
        }
        precondition = {
            'precondition_type': 'virt',
            'name'             : 'automatically generated Xen test',
            'host'             : host,
            'guests'           : guests,
        }
        return precondition

    def __write_subjectinfo(self):
        """
        Write the test subject description to a file

        Write a dictionary with the test subject name in YAML format to
        a file specified in the environment variable $TAPPER_TEMARE.
        The file is not written when the variable is not set.
        """
        subject_name = self.testrun.subject['name']
        if self.testrun.subject['bitness'] == 1:
            subject_name = subject_name + '-64'
        else:
            subject_name = subject_name + '-32'
        data = {'subject': subject_name}

        try:
            if os.environ.has_key('TAPPER_TEMARE'):
                infofile = open(os.environ['TAPPER_TEMARE'], 'w')
                infofile.write(yaml.safe_dump(data, default_flow_style=False))
                infofile.close()
        except IOError:
            raise ValueError('Failed to write test subject description file.')

    def gen_precondition(self):
        """
        Generate and output an Tapper virt precondition

        Calls the appropriate method for the test subject, which was
        determined by calling the test run generator, and writes the
        generated precondition in YAML format to STDOUT.

        At the end, a file with the test subject description is written
        and the tests are marked as done in the database.
        """
        precondition = ''
        subject = self.testrun.subject['name']
        if subject.startswith('xen'):
            precondition = (self.gen_precondition_xen())
        elif subject.startswith('autoinstall'):
            precondition = self.gen_precondition_autoinstall()
        else:
            raise ValueError('Invalid test subject.')
        sys.stdout.write(yaml.safe_dump(precondition,
                default_flow_style=False, width=500))
        self.__write_subjectinfo()
        self.testrun.do_finalize()


if __name__ == '__main__':
    pass
