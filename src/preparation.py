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
import datetime
import time
from subprocess import Popen, PIPE, STDOUT
from socket import gethostname
from os.path import basename
from stat import S_IMODE, S_IXUSR, S_IXGRP, S_IXOTH
from checks import chk_hostname, chk_subject
from config import kvm, svm, formats, svmscript, copyscript,        \
                   osimage, svmpath, nfshost, suiteimage,           \
                   builddir, buildarchs, buildpattern, imagepath,   \
                   tstimeout, kvmexecpath, kvmimage, kvmconfig,     \
                   kvmkernelrepo, kvmuserspacerepo, kvmbuildscript


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


class HostPreparation(BasePreparation):
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
            test['mntfile'] = '%03d.img' % (test['runid'], )
            test['format'] = formats[test['format']]
            test['imgbasename'] = basename(test['image'])
        self.stage = 'Check xend status'
        self.do_command('/usr/sbin/xend status')
        self.stage = 'Check for running guests'
        self.do_command('test `/usr/sbin/xm list |wc -l` -eq 2')
        self.stage = 'Cleanup old guest configs and images'
        self.do_command('/bin/rm -f /xen/images/*.svm /xen/images/*.img')
        self.stage = 'Generate guest configuration files'
        for test in self.testrun.tests:
            self.do_command((svmscript % test) % ((svm % test), ))
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
            test['mntfile'] = '%03d.img' % (test['runid'], )
            test['imgbasename'] = basename(test['image'])
        self.stage = 'Check for kernel modules'
        self.do_command('/sbin/modprobe kvm kvm-amd kvm-intel && '
                '/sbin/lsmod | /bin/grep -q "^kvm "')
        self.stage = 'Check for running guests'
        self.do_command(
                'test `ps -C qemu-kvm -C qemu-system-x86_64 | wc -l` -eq 1')
        self.stage = 'Cleanup old guest configs and images'
        self.do_command('/bin/rm -f /xen/images/*.svm /xen/images/*.img')
        self.stage = 'Copying testsuite image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % ((suiteimage, test['mntfile']) * 2))
        self.stage = 'Copying guest image files'
        for test in self.testrun.tests:
            self.do_command(copyscript % tuple([test['image']] * 4))
        self.stage = 'Starting guests'
        for test in self.testrun.tests:
            test.update(executable='/usr/local/bin/qemu-system-x86_64')
            command = kvm % test
            test.update(executable='/usr/bin/qemu-kvm')
            command += ' || %s' % (kvm % test, )
            self.do_command(command)
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
    """

    def __init__(self, host):
        self.build = None
        self.builddir = None
        self.guestconfigs = {}
        self.host = chk_hostname(host)
        if gethostname() != nfshost:
            raise ValueError(
                    'This command is meant to be run on %s by Artemis.\n'
                    'Please update the config module if the Artemis '
                    'host has changed.' % (nfshost, ))
        self.testrun = generator.TestRunGenerator(self.host, auto=True)

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
            raise ValueError('Build directory does not exist.')
        if len(builds) < 1:
            raise ValueError(
                    'No builds available for %s on %s.' % (version, arch))
        builds.sort()
        self.build = builds.pop()

    @staticmethod
    def __write_config(filename, path, test, template):
        """Write a guest config file or start script to the specified location

        Expects:
            filename - Name of the file to be written
            path     - Location to store the file into
            test     - Dictionary of a single guest test
            template - Template of the files content
        """
        filepath = '%s/%s' % (path, filename)
        try:
            cfgfile = open(filepath, 'w')
            cfgfile.write(template % test)
        except:
            raise ValueError('Failed to write guest config files.')
        finally:
            cfgfile.close()
        if filepath.endswith('.sh'):
            oldmode = S_IMODE(os.stat(filepath).st_mode)
            newmode = oldmode | S_IXUSR | S_IXGRP | S_IXOTH
            os.chmod(filepath, newmode)

    def gen_guest_configs(self):
        """Write guest configuration files

        Guest configuration files get written into a directory which is
        specified through config.svmpath or config.kvmexecpath.
        Naming convention is

            [0-9]{3}-${hostname}-${date +%s}.(svm|sh)

        Config files from prior runs will be overwritten.
        """
        timestamp = time.mktime(datetime.datetime.utcnow().timetuple())
        for test in self.testrun.tests:
            prefix = '%03d-%s-%ld' % (test['runid'], self.host, timestamp)
            test['mntfile'] = '%s.img' % (prefix, )
            test['format'] = formats[test['format']]
            test['imgbasename'] = basename(test['image'])
            if self.testrun.subject['name'].startswith('xen'):
                test['svmfile'] = '%s.svm' % (prefix, )
                self.__write_config(test['svmfile'], svmpath, test, svm)
            elif self.testrun.subject['name'].startswith('kvm'):
                test['datadir'] = '/kvm'
                test['kvmexec'] = '%s.sh' % (prefix, )
                self.__write_config(test['kvmexec'], kvmexecpath, test, kvm)
            else:
                raise ValueError('Invalid test subject.')

    def gen_precondition(self):
        """Prepare a test run and generate a precondition YAML string

        Just calls the appropriate method for the test subject which was
        determined by calling the test run generator.
        """
        if self.testrun.subject['name'].startswith('xen'):
            self.gen_precondition_xen()
        elif self.testrun.subject['name'].startswith('kvm'):
            self.gen_precondition_kvm()
        else:
            raise ValueError('Invalid test subject.')

    def gen_precondition_xen(self):
        """Prepare a Xen test run and generate a precondition YAML string

        Find latest build of the test subject, generate guest
        configurations, write a precondition string to STDOUT, and finally
        mark the guest tests as done in the database.
        """
        self.get_latest_build()
        self.gen_guest_configs()
        osimagefile = osimage[self.testrun.subject['bitness']]
        testprogram = '/opt/artemis/bin/artemis_testsuite_dom0_meta.sh'
        installpkg = 'artemisutils/sles10/xen_installer_suse.tar.gz'
        precondition = {
            'precondition_type':   'virt',
            'name':                'automatically generated Xen test'}
        precondition['host'] = {
                'root': {
                    'precondition_type':    'image',
                    'mount':                '/',
                    'partition':            'testing',
                    'arch':                 'linux64',
                    'image':                osimagefile},
                'testprogram': {
                    'execname':             testprogram,
                    'timeout_testprogram':  tstimeout},
                'preconditions': [
                    {'precondition_type':   'package',
                     'filename':            self.builddir + '/' + self.build},
                    {'precondition_type':   'package',
                     'filename':            installpkg},
                    {'precondition_type':   'exec',
                     'filename':            '/bin/xen_installer_suse.pl'}]
                }
        precondition['guests'] = []
        for test in self.testrun.tests:
            imagefile = '%s/%s' % (imagepath, test['image'])
            mountfile = '/xen/images/%s' % (test['mntfile'], )
            svmsource = '%s:%s/%s' % (nfshost, svmpath, test['svmfile'])
            svmdest   = '%s/%s' % ('/xen/images/', test['svmfile'])
            if test['bitness'] == 1:
                arch = 'linux64'
            else:
                arch = 'linux32'
            guest = {
                'root': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 imagefile,
                    'dest':                 '/xen/images/',
                    'mountfile':            mountfile,
                    'mounttype':            'raw',
                    'arch'     :            arch
                    },
                'config': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 svmsource,
                    'dest':                 '/xen/images/',
                    'svm':                  svmdest},
                'testprogram': {
                    'execname':             test['testcommand'],
                    'timeout_testprogram':  tstimeout}
                }
            precondition['guests'].append(guest)
        sys.stdout.write(yaml.dump(precondition, default_flow_style=False))
        self.testrun.do_finalize()

    def gen_precondition_kvm(self):
        """Prepare a KVM test run and generate a precondition YAML string

        Generate guest configurations, write a precondition string to STDOUT,
        and finally mark the guest tests as done in the database.
        """
        self.gen_guest_configs()
        testprogram = '/opt/artemis/bin/artemis_testsuite_dom0_meta.sh'
        buildexec = '/bin/%s' % (basename(kvmbuildscript), )
        precondition = {
            'precondition_type':   'virt',
            'name':                'automatically generated KVM test'}
        precondition['host'] = {
                'root': {
                    'precondition_type':    'image',
                    'mount':                '/',
                    'partition':            'testing',
                    'arch':                 'linux64',
                    'image':                kvmimage},
                'testprogram': {
                    'execname':             testprogram,
                    'timeout_testprogram':  tstimeout},
                'preconditions': [
                    {'precondition_type':   'repository',
                     'type':                'git',
                     'url':                 kvmkernelrepo},
                    {'precondition_type':   'repository',
                     'type':                'git',
                     'url':                 kvmuserspacerepo},
                    {'precondition_type':   'copyfile',
                     'protocol':            'local',
                     'name':                kvmconfig,
                     'dest':                '/kvm/'},
                    {'precondition_type':   'copyfile',
                     'protocol':            'local',
                     'name':                kvmbuildscript,
                     'dest':                '/bin/'},
                    {'precondition_type':   'exec',
                     'filename':            buildexec}]
                }
        precondition['guests'] = []
        for test in self.testrun.tests:
            imagefile = '%s/%s' % (imagepath, test['image'])
            mountfile = '/kvm/images/%s' % (test['mntfile'], )
            execsource = '%s:%s/%s' % (nfshost, kvmexecpath, test['kvmexec'])
            execdest   = '/kvm/images/%s' % (test['kvmexec'], )
            if test['bitness'] == 1:
                arch = 'linux64'
            else:
                arch = 'linux32'
            guest = {
                'root': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 imagefile,
                    'dest':                 '/kvm/images/',
                    'mountfile':            mountfile,
                    'mounttype':            'raw',
                    'arch'     :            arch
                    },
                'config': {
                    'precondition_type':    'copyfile',
                    'protocol':             'nfs',
                    'name':                 execsource,
                    'dest':                 execdest,
                    'exec':                 execdest},
                'testprogram': {
                    'execname':             test['testcommand'],
                    'timeout_testprogram':  tstimeout}
                }
            precondition['guests'].append(guest)
        sys.stdout.write(yaml.dump(precondition, default_flow_style=False))
        self.testrun.do_finalize()


if __name__ == '__main__':
    pass
