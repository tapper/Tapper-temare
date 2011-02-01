#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Classes for CLI commands providing command aliases,
   short description, usage information, argument descriptions,
   and a method to actually run the command
"""
import sys
import dbops
import preparation
import version
from subprocess import Popen, PIPE
from checks import chk_arg_count, chk_bitness, chk_hostname, chk_subject


def do_list(listing, ordering):
    """Print a plain text table of a given database query

    Substitutes column names and boolean values with human readable strings.
    Arguments:
        listing  -- A tuple of dictionaries containing the
                    resulting lines of a database query
        ordering -- A list of column names in the order they are
                    supposed to be displayed
    """
    headings = {
            'host_name'   : 'Host',
            'host_cores'  : 'CPU Cores',
            'host_memory' : 'Memory',
            'image_name'  : 'Guest Image',
            'image_format': 'Format',
            'os_type_name': 'OS Type',
            'subject_name': 'Test Subject',
            'subject_prio': 'Priority',
            'test_name'   : 'Test Program',
            'test_command': 'Command',
            'timeout'     : 'Timeout',
            'runtime'     : 'Requested runtime',
            'vendor_name' : 'Vendor',
            'is_64bit'    : 'Bitness',
            'is_bigmem'   : 'BigMem',
            'is_enabled'  : 'State',
            'key'         : 'Key',
            'value'       : 'Value',
            'is_smp'      : 'SMP'}
    substitutions = {
            'is_64bit'  : {0: '32',       1: '64'},
            'is_bigmem' : {0: 'no',       1: 'yes'},
            'is_enabled': {0: 'disabled', 1: 'enabled'},
            'is_smp'    : {0: 'no',       1: 'yes'}}
    width = {}
    for key, value in headings.iteritems():
        width[key] = len(str(value))
    for index in range(0, len(listing)):
        for key, value in listing[index].iteritems():
            if key == 'host_memory':
                value = '%s MB' % (value, )
                listing[index][key] = value
            elif key in substitutions.keys():
                value = substitutions[key][value]
                listing[index][key] = value
            if width[key] < len(str(value)):
                width[key] = len(str(value))
    colformat = []
    header = ()
    separator = ()
    for column in ordering:
        colformat.append('%%-%ds' % (width[column], ))
        header += (headings[column], )
        separator += ('-' * width[column], )
    separator = '+-' + '-+-'.join(colformat) % separator +'-+\n'
    header = '| ' + ' | '.join(colformat) % header + ' |\n'
    sys.stdout.write('%s%s%s' % (separator, header, separator))
    for line in listing:
        values = ()
        for column in ordering:
            values += (line[column], )
        sys.stdout.write('| ' + ' | '.join(colformat) % values + ' |\n')
    sys.stdout.write(separator)


class TemareCommand:
    """Base class for CLI commands
    """

    def __init__(self, base):
        self.base = base
        self.names = []
        self.usage = ''
        self.summary = ''
        self.description = None

    def get_names(self):
        """@return: A list of command aliases
        """
        return self.names

    def get_usage(self):
        """@return: A usage string for the command, including arguments
        """
        return self.usage

    def get_summary(self):
        """@return: A one line summary of what the command does
        """
        return self.summary

    def get_description(self):
        """@return: Detailed description of command parameters
        """
        return self.description

    def do_command(self, args):
        """Execute the actual command and raise an error on failure
        """
        pass


class HelpCommand(TemareCommand):
    """Output help and descriptions for CLI commands
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['help']
        self.usage = '[COMMAND]'
        self.summary = 'Show detailed usage information about a command'

    def get_command_usage(self, command):
        """@return: Usage information string for a given command.
        """
        usage = self.base.commands[command].get_usage()
        return 'Usage: %s %s %s\n' % (self.base.scriptname, command, usage)

    def do_overview(self):
        """Print an overview of all available commands
        """
        summaries = []
        for name, cmd in self.base.commands.iteritems():
            summaries.append('    %-14s  %s\n' % (name, cmd.get_summary()))
        summaries.sort()
        sys.stdout.write('Usage: %s COMMAND ARGUMENTS...\n\n' \
                'Available commands:\n' % (self.base.scriptname, ))
        for line in summaries:
            sys.stdout.write(line)

    def do_command_help(self, command):
        """Print detailed help information for a given command
        """
        summary = self.base.commands[command].get_summary()
        usage = self.get_command_usage(command)
        description = self.base.commands[command].get_description()
        sys.stdout.write('%s\n%s' % (summary, usage))
        if description != None:
            sys.stdout.write('Arguments Description:\n%s\n' %
                    (description, ))

    def do_command(self, args = ()):
        """Display some help depending on the given arguments
        """
        if len(args) == 0:
            self.do_overview()
        elif len(args) != 1:
            raise ValueError('Wrong number of arguments.')
        elif args[0] in self.base.commands.keys():
            self.do_command_help(args[0])
        else:
            raise ValueError('No such command.')


class InitDbCommand(TemareCommand):
    """Initialize a new database
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['initdb']
        self.summary = 'Initialize the schedule database'

    def do_command(self, args):
        """Validate the number of given arguments and
           initialize the database
        """
        chk_arg_count(args, 0)
        dbops.init_database()


class HostPrepCommand(TemareCommand):
    """Output guest configurations for a new test run on a given host
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.failed = 0
        self.names = ['hostprep']
        self.usage = 'HOSTNAME...'
        self.summary = 'Prepare and start testruns on the specified hosts'
        self.description = \
            '    HOSTNAME  Name of the host'

    def do_command(self, args):
        """Validate the number of given arguments and
           generate guest configurations
        """
        hostlist = []
        threads = []
        environment = ''
        getenv = '(grep -q "^kvm " /proc/modules && echo "kvm") || '         \
                 '(/usr/sbin/xend status >/dev/null 2>&1 && echo "xen") || ' \
                 'echo "bare"'
        if len(args) == 0:
            raise ValueError('No arguments given.')
        sys.stdout.write(
                'Starting to prepare hosts. '
                'Please wait, this may take a while...\n')
        for host in args:
            host = chk_hostname(host)
            if host not in hostlist:
                hostlist.append(host)
                process = Popen(['/usr/bin/ssh',
                        '-o PasswordAuthentication=no', 'root@%s' % (host, ),
                        getenv], stderr=None, stdout=PIPE)
                retval = process.wait()
                if retval == 0:
                    output = process.communicate()[0].strip().split('\n')
                    if len(output) == 1 and output[0] in ('xen', 'kvm'):
                        environment = output[0]
                if environment == 'xen':
                    threads.append(preparation.XenHostPreparation(self, host))
                elif environment == 'kvm':
                    threads.append(preparation.KvmHostPreparation(self, host))
                else:
                    self.failed = 1
                    sys.stderr.write(
                            'Preparation of host %s failed\n'
                            'Reason:\n'
                            'Could not determine the test environment.\n'
                            % (host, ))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if self.failed == 1:
            raise ValueError('Preparation of some hosts failed.')


class HostAddCommand(TemareCommand):
    """Add a new host to the pool of available boxes to test on
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['hostadd']
        self.usage = 'HOSTNAME MEMORY CORES BITNESS'
        self.summary = 'Add a host to use for testing'
        self.description = \
            '    HOSTNAME  Name of the host\n' \
            '    MEMORY    Amount of memory in MB available on this system\n' \
            '    CORES     Amount of CPU cores available on this system\n' \
            '    BITNESS   Capability to run 64-bit guests'

    def do_command(self, args):
        """Add a host to the database
        """
        hostops = dbops.Hosts()
        hostops.add(args)


class HostDelCommand(TemareCommand):
    """Remove a host from the pool of available boxes to test on
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['hostdel']
        self.usage = 'HOSTNAME'
        self.summary = 'Entirely remove a host from test scheduling'
        self.description = \
            '    HOSTNAME  Name of the host'

    def do_command(self, args):
        """Remove the host from the database
        """
        hostops = dbops.Hosts()
        hostops.delete(args)


class HostModCommand(TemareCommand):
    """Modify the configuration of an existing host
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['hostmod']
        self.usage = 'HOSTNAME mem|cores|bits ARGUMENT'
        self.summary = 'Modify a hosts configuration'
        self.description = \
            '    HOSTNAME  Name of the host\n' \
            '    ARGUMENT  Value of the configuration'

    def do_command(self, args):
        """Validate the number of given arguments and
            update the host configuration
        """
        chk_arg_count(args, 3)
        hostname, command, value = args
        args = (hostname, value)
        hostops = dbops.Hosts()
        if command == 'mem':
            hostops.memory(args)
        elif command == 'cores':
            hostops.cores(args)
        elif command == 'bits':
            hostops.bitness(args)
        else:
            raise ValueError('Unknown host configuration.')


class HostStateCommand(TemareCommand):
    """Enable or disable testing on a specified host
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['hoststate']
        self.usage = 'HOSTNAME enable|disable'
        self.summary = 'Enable or disable test scheduling for a host'
        self.description = \
            '    HOSTNAME  Name of the host'

    def do_command(self, args):
        """Validate the number of given arguments and set the hosts state
        """
        hostops = dbops.Hosts()
        hostops.state(args)


class HostListCommand(TemareCommand):
    """Display a list of all hosts, their configurations, and states
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['hostlist']
        self.summary = 'Get a list of all hosts and their current state'

    def do_command(self, args):
        """Print a list of all hosts and their properties
        """
        hostops = dbops.Hosts()
        listing = hostops.list(args)
        ordering = ['host_name', 'host_memory', 'host_cores',
                'is_64bit', 'is_enabled']
        do_list(listing, ordering)


class ImageAddCommand(TemareCommand):
    """Add a new image file to the testing schedules
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['imageadd']
        self.usage = 'FILENAME FORMAT VENDOR OSTYPE BITNESS BIGMEM SMP'
        self.summary = 'Add a new guest image to the schedule'
        self.description = \
            '    FILENAME  Filename of the guest image\n' \
            '    FORMAT    Format of the guest image\n' \
            '    VENDOR    Name of the distributor or vendor\n' \
            '    OSTYPE    Operating system type of the guest image\n' \
            '    BITNESS   Bitness of the operating system\n' \
            '    BIGMEM    Capability to address more than 4 GB of memory\n' \
            '    SMP       Capability to use more than one processor'

    def do_command(self, args):
        """Add a guest image to the database
        """
        imageops = dbops.Images()
        imageops.add(args)


class ImageDelCommand(TemareCommand):
    """Remove an image file from the testing schedules
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['imagedel']
        self.usage = 'FILENAME'
        self.summary = 'Remove a guest image from the schedule'
        self.description = \
            '    FILENAME  Filename of the guest image'

    def do_command(self, args):
        """Remove a guest image from the database
        """
        imageops = dbops.Images()
        imageops.delete(args)


class ImageStateCommand(TemareCommand):
    """Enable or disable scheduling of the specified image file
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['imagestate']
        self.usage = 'FILENAME enable|disable'
        self.summary = 'Disable or enable the scheduling of a guest image'
        self.description = \
            '    FILENAME  Filename of the guest image'

    def do_command(self, args):
        """Validate the number of given arguments and
           set the state of the guest image
        """
        imageops = dbops.Images()
        imageops.state(args)


class ImageListCommand(TemareCommand):
    """Display a list of all image files, their properties and states
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['imagelist']
        self.summary = 'Get a list of all images and their current state'

    def do_command(self, args):
        """Print a list of all guest images and their current state
        """
        imageops = dbops.Images()
        listing = imageops.list(args)
        ordering = ['image_name', 'image_format', 'vendor_name', 'os_type_name',
                'is_64bit', 'is_bigmem', 'is_smp', 'is_enabled']
        do_list(listing, ordering)


class OsAddCommand(TemareCommand):
    """Add a new operting system type
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['osadd']
        self.usage = 'OSTYPE'
        self.summary = 'Add a new operating system type'
        self.description = \
            '    OSTYPE  Name of the operating system type'

    def do_command(self, args):
        """Add an OS type to the database
        """
        ostypeops = dbops.OsTypes()
        ostypeops.add(args)


class OsDelCommand(TemareCommand):
    """Remove an operating system type
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['osdel']
        self.usage = 'OSTYPE'
        self.summary = 'Remove an operating system type'
        self.description = \
            '    OSTYPE  Name of the operating system type'

    def do_command(self, args):
        """Remove an OS type from the database
        """
        ostypeops = dbops.OsTypes()
        ostypeops.delete(args)


class OsListCommand(TemareCommand):
    """Display a list of all operating system types
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['oslist']
        self.summary = 'Get a list of all operating system types'

    def do_command(self, args):
        """Print a list of all operating system types
        """
        ostypeops = dbops.OsTypes()
        listing = ostypeops.list(args)
        ordering = ['os_type_name']
        do_list(listing, ordering)


class TestAddCommand(TemareCommand):
    """Add a new test program to the schedule
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['testadd']
        self.usage = 'TESTNAME OSTYPE TESTCOMMAND RUNTIME TIMEOUT'
        self.summary = 'Add a new test to the schedule'
        self.description = \
            '    TESTNAME     Name of the test program\n' \
            '    OSTYPE       Name of the operating system type\n' \
            '    TESTCOMMAND  Command to start the test program\n' \
            '    RUNTIME      Runtime for testsuite (seconds)\n' \
            '    TIMEOUT      Timeout for testsuite (seconds)'

    def do_command(self, args):
        """Add a test program to the database
        """
        testops = dbops.Tests()
        testops.add(args)


class TestDelCommand(TemareCommand):
    """Remove a test program from the schedule
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['testdel']
        self.usage = 'TESTNAME OSTYPE'
        self.summary = 'Remove a test from the schedule'
        self.description = \
            '    TESTNAME  Name of the test program\n' \
            '    OSTYPE    Name of the operating system type'

    def do_command(self, args):
        """Remove a test program from the database
        """
        testops = dbops.Tests()
        testops.delete(args)


class TestListCommand(TemareCommand):
    """Display a list of all test programs and their targeted OS
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['testlist']
        self.summary = 'Get a list of all tests'

    def do_command(self, args):
        """Print a list of all test programs and their targeted OS
        """
        testops = dbops.Tests()
        listing = testops.list(args)
        ordering = ['test_name', 'os_type_name',
                'test_command', 'runtime', 'timeout']
        do_list(listing, ordering)


class TestSubjectPrepCommand(TemareCommand):
    """Write guest configurations and output YAML precondition
    for a new test run on a given host to be performed through Tapper
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['subjectprep']
        self.usage = 'HOSTNAME [SUBJECT BITNESS]'
        self.summary = 'Create guest configs and output YAML precondition'
        self.description = \
            '    HOSTNAME  Name of the host\n' \
            '    SUBJECT   Name of a specific test subject (optional)\n' \
            '    BITNESS   Bitness of the test subject\n' \
            '              (required if a subject is specified)'

    def do_command(self, args):
        """Validate the number of given arguments, write guest configurations,
        and ouput a YAML precondition string
        """
        if len(args) == 1:
            hostname = chk_hostname(args[0])
            subjectops = preparation.SubjectPreparation(hostname)
            subjectops.gen_precondition()
        elif len(args) == 3:
            hostname = chk_hostname(args[0])
            subject = chk_subject(args[1])
            bitness = chk_bitness(args[2])
            subjectops = preparation.SubjectPreparation(
                    hostname, subject, bitness)
            subjectops.gen_precondition()
        else:
            raise ValueError('Wrong number of arguments.')


class TestSubjectAddCommand(TemareCommand):
    """Add a new test subject to the schedule
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['subjectadd']
        self.usage = 'SUBJECT BITNESS PRIORITY'
        self.summary = 'Add a new test subject to the schedule'
        self.description = \
            '    SUBJECT   Descriptive name of the test subject\n' \
            '    BITNESS   Bitness of the test subject\n' \
            '    PRIORITY  Tapper queue priority for the test subject'

    def do_command(self, args):
        """Add a test subject to the database
        """
        subjectops = dbops.TestSubjects()
        subjectops.add(args)
        sys.stdout.write(
                'The subject was added, but not yet activated.\n'
                'Use the subjectstate command to activate it.\n')


class TestSubjectDelCommand(TemareCommand):
    """Remove a test subject from the schedule
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['subjectdel']
        self.usage = 'SUBJECT BITNESS'
        self.summary = 'Remove a test subject from the schedule'
        self.description = \
            '    SUBJECT  Descriptive name of the test subject\n' \
            '    BITNESS  Bitness of the test subject'

    def do_command(self, args):
        """Remove a test subject from the database
        """
        subjectops = dbops.TestSubjects()
        subjectops.delete(args)


class TestSubjectStateCommand(TemareCommand):
    """Enable or disable scheduling of the specified test subject
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['subjectstate']
        self.usage = 'SUBJECT BITNESS enable|disable [PRIORITY]'
        self.summary = 'Disable or enable the scheduling of a test subject'
        self.description = \
            '    SUBJECT   Descriptive name of the test subject\n' \
            '    BITNESS   Bitness of the test subject\n' \
            '    PRIORITY  Tapper queue priority for the test subject\n' \
            '              (optional, only valid with enable command'

    def do_command(self, args):
        """Validate the number of given arguments and
           set the state of the test subject
        """
        subjectops = dbops.TestSubjects()
        subjectops.state(args)


class TestSubjectListCommand(TemareCommand):
    """Display a list of all test subjects, their properties, and states
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['subjectlist']
        self.summary = \
                'Get a list of all test subjects and their current state'

    def do_command(self, args):
        """Print a list of all test subjects and their current state
        """
        subjectops = dbops.TestSubjects()
        listing = subjectops.list(args)
        ordering = ['subject_name', 'is_64bit', 'is_enabled', 'subject_prio']
        do_list(listing, ordering)


class VendorAddCommand(TemareCommand):
    """Add a new operating system vendor
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['vendoradd']
        self.usage = 'VENDOR'
        self.summary = 'Add a new vendor'
        self.description = \
            '    VENDOR  Name of operating system vendor'

    def do_command(self, args):
        """Add an OS vendor to the database
        """
        vendorops = dbops.Vendors()
        vendorops.add(args)


class VendorDelCommand(TemareCommand):
    """Remove an operating system vendor
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['vendordel']
        self.usage = 'VENDOR'
        self.summary = 'Remove a vendor'
        self.description = \
            '    VENDOR  Name of operating system vendor'

    def do_command(self, args):
        """Remove an OS vendor from the database
        """
        vendorops = dbops.Vendors()
        vendorops.delete(args)


class VendorListCommand(TemareCommand):
    """Display a list of all operating system vendors
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['vendorlist']
        self.summary = 'Get a list of all vendors'

    def do_command(self, args):
        """Print a list of all OS vendors
        """
        vendorops = dbops.Vendors()
        listing = vendorops.list(args)
        ordering = ['vendor_name']
        do_list(listing, ordering)


class VersionCommand(TemareCommand):
    """Print the temare version number
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['version']
        self.summary = 'Print the temare version number and exit'

    def do_command(self, args):
        """Validate the number of given arguments and
           print the version number
        """
        chk_arg_count(args, 0)
        sys.stdout.write('temare %s\n' % (version.__version__, ))


class CompletionAddCommand(TemareCommand):
    """Add a new completion entry
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['completionadd']
        self.usage = 'SUBJECT BITNESS KEY VALUE'
        self.summary = 'Add a new completion entry'
        self.description = \
            '    SUBJECT  Name of the test subject\n' \
            '    BITNESS  Bitness of the test subject\n' \
            '    KEY      Name of the variable\n' \
            '    VALUE    Subtitution for the key'

    def do_command(self, args):
        """Add a completion entry to the database
        """
        compops = dbops.Completions()
        compops.add(args)


class CompletionDelCommand(TemareCommand):
    """Remove an existing completion entry
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['completiondel']
        self.usage = 'SUBJECT BITNESS KEY'
        self.summary = 'Delete an existing completion entry'
        self.description = \
            '    SUBJECT  Name of the test subject\n' \
            '    BITNESS  Bitness of the test subject\n' \
            '    KEY      Name of the variable as present in the template'

    def do_command(self, args):
        """Remove a completion entry from the database
        """
        compops = dbops.Completions()
        compops.delete(args)


class CompletionListCommand(TemareCommand):
    """Display a list of all completion entries
    """

    def __init__(self, base):
        TemareCommand.__init__(self, base)
        self.names = ['completionlist']
        self.usage = '[SUBJECT BITNESS]'
        self.summary = 'List completions for a specific or for all subjects'
        self.description = \
            '    SUBJECT  Name of the test subject    (optional)\n' \
            '    BITNESS  Bitness of the test subject (optional)\n'

    def do_command(self, args):
        """Print a list of all completion entries for all subjects,
           or optionally for one specific subject
        """
        compops = dbops.Completions()
        listing = compops.list(args)
        ordering = ['subject_name', 'is_64bit', 'key', 'value']
        do_list(listing, ordering)
