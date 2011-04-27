"""
Interface to handle Tapper Queues for test subjects
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
from subprocess import Popen, PIPE
from tempfile import mkstemp
from config import debug


class TapperQueue:
    """
    Interface to handle Tapper Queues for test subjects
    """

    def __init__(self, subject, bitness):
        """
        @param subject: The name of the test subject
        @type  subject: str
        @param bitness: Whether the test subject is 64-bit
        @type  bitness: bool
        """
        self.subject = str(subject)
        self.bitness = ('32', '64')[int(bool(bitness))]
        self.queue = '%s-%s' % (self.subject, self.bitness)

    @staticmethod
    def __error_handler(msg, cmd, rcode, stdout, stderr):
        """
        Constructs a verbose error message and raises an error with it

        @param msg   : Generic message about the error
        @type  msg   : str
        @param cmd   : The failing command
        @type  cmd   : str
        @param rcode : Returncode of the command
        @type  rcode : int
        @param stdout: Stdout output of the command
        @type  stdout: str
        @param stderr: Stderr output of the command
        @type  stderr: str
        @raise       : ValueError
        """
        message = \
                '%s\n' \
                'Following command failed:\n' \
                '%s\n' \
                'Standard output:\n' \
                '%s\n' \
                'Standard error:\n' \
                '%s\n' \
                'Return code:\n' \
                '%s' \
                % (msg, cmd, stdout, stderr, rcode)
        raise ValueError(message)

    @staticmethod
    def __exec_command(cmd):
        """
        Execute a given command locally

        Return its exit code, as well as its output on stdout and stderr.

        @param cmd: The command to be executed
        @type  cmd: str
        @return   : A tuple of returncode, stdout, and stderr in that order
        @rtype    : tuple
        """
        if debug:
            sys.stderr.write('Debug mode, skipped command "%s"\n' % (cmd, ))
            stdout, stderr = ('DEBUG MODE', '')
            returncode = 0
        else:
            process = Popen(['/bin/bash', '-c', cmd], stderr=PIPE, stdout=PIPE)
            stdout, stderr = process.communicate()
            returncode = process.returncode
        return returncode, stdout, stderr

    def __create_testrun(self):
        """
        Schedule a producer testrun for the Tapper queue

        Writes the precondition in YAML format to a temporary file, creates
        the testrun with the auto_rerun option, and removes the temporary
        file again.

        @raise: ValueError
        """
        filename = None
        precondition = {
            'precondition_type': 'produce',
            'producer'         : 'Temare',
            'subject'          : self.subject,
            'bitness'          : self.bitness,
        }
        try:
            tmpfile, filename = mkstemp()
            os.write(tmpfile, yaml.safe_dump(precondition,
                    default_flow_style=False, width=500))
            os.close(tmpfile)
        except (OSError, IOError):
            if filename and os.path.exists(filename):
                os.unlink(filename)
            raise ValueError('Failed to write testrun precondition.')
        cmd = ('tapper-testrun new --queue="%s" '
                '--auto_rerun --macroprecond="%s"') % (self.queue, filename)
        rcode, stdout, stderr = self.__exec_command(cmd)
        os.unlink(filename)
        if rcode != 0:
            msg = 'Failed to create a testrun for the Tapper queue.'
            self.__error_handler(msg, cmd, rcode, stdout, stderr)

    def list(self):
        """
        List the Tapper queue associated with the test subject

        @return: Tapper information about the queue, or empty string
        @rtype : str
        @raise : ValueError
        """
        cmd = 'tapper-testrun listqueue --name="%s"'
        rcode, stdout, stderr = self.__exec_command(cmd % (self.queue, ))
        if rcode != 0:
            msg = 'Failed to check for the Tapper queue.'
            self.__error_handler(msg, cmd, rcode, stdout, stderr)
        return stdout

    def create(self, priority):
        """
        Create an Tapper queue associated with the test subject

        Creates the queue and schedules a producer testrun with the
        auto_rerun option.

        @param priority: Tapper bandwidth for the test subject
        @type  priority: int
        @raise         : ValueError
        """
        cmd = 'tapper-testrun newqueue --name="%s" --active --priority="%s"'
        cmd = cmd % (self.queue, priority)
        rcode, stdout, stderr = self.__exec_command(cmd)
        if rcode != 0:
            msg = 'Failed to create the Tapper queue.'
            self.__error_handler(msg, cmd, rcode, stdout, stderr)
        self.__create_testrun()

    def update(self, state, priority=0):
        """
        Update the Tapper queue associated with the test subject

        Update the state and optionally the priority (Tapper bandwidth)
        of the Tapper queue associated with the test subject.

        @param state   : Status of the queue (active or not active)
        @type  state   : bool
        @param priority: Tapper bandwidth for the test subject (optional)
        @type  priority: int
        @raise         : ValueError
        """
        cmd = 'tapper-testrun updatequeue --name="%s"' % (self.queue, )
        if state:
            cmd = ' '.join([cmd, '--active'])
        else:
            cmd = ' '.join([cmd, '--noactive'])
        if priority > 0:
            cmd = ' '.join([cmd, '--priority="%s"' % (priority, )])
        rcode, stdout, stderr = self.__exec_command(cmd)
        if rcode != 0:
            msg = 'Failed to update the Tapper queue.'
            self.__error_handler(msg, cmd, rcode, stdout, stderr)

    def delete(self):
        """
        Remove the Tapper queue associated with the test subject

        The operation is skipped silently if no such queue exists.

        @raise : ValueError
        """
        if self.list():
            cmd = 'tapper-testrun deletequeue --name="%s" --really'
            rcode, stdout, stderr = self.__exec_command(cmd % (self.queue, ))
            if rcode != 0:
                msg = 'Failed to remove the Tapper queue.'
                self.__error_handler(msg, cmd, rcode, stdout, stderr)

    def enable(self, priority):
        """
        Enable the Tapper queue for the test subject

        If an Tapper queue already exists, its status and its priority
        settings are updated. Otherwise, a new Tapper queue with the
        appropriate settings is getting created and a producer testrun
        is scheduled for that queue.

        @param priority: Tapper bandwidth for the test subject
        @type  priority: int
        @raise         : ValueError
        """
        if self.list():
            self.update(True, int(priority))
        else:
            self.create(int(priority))

    def disable(self):
        """
        Disable the Tapper queue for the test subject

        If an Tapper queue already exists, its status is set to "noactive".

        @raise: ValueError
        """
        if self.list():
            self.update(False)
