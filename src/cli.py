#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Main class for the command line interface
"""
import sys
from os.path import basename
import clicommands


class TemareCli:
    """Main class for the command line interface
    """

    def __init__(self, args):
        self.commands = {}
        self.add_command(clicommands.HelpCommand(self))
        self.add_command(clicommands.InitDbCommand(self))
        self.add_command(clicommands.HostAddCommand(self))
        self.add_command(clicommands.HostDelCommand(self))
        self.add_command(clicommands.HostStateCommand(self))
        self.add_command(clicommands.HostListCommand(self))
        self.add_command(clicommands.HostPrepCommand(self))
        self.add_command(clicommands.ImageAddCommand(self))
        self.add_command(clicommands.ImageDelCommand(self))
        self.add_command(clicommands.ImageStateCommand(self))
        self.add_command(clicommands.ImageListCommand(self))
        self.add_command(clicommands.TestAddCommand(self))
        self.add_command(clicommands.TestDelCommand(self))
        self.add_command(clicommands.TestListCommand(self))
        self.add_command(clicommands.TestSubjectAddCommand(self))
        self.add_command(clicommands.TestSubjectDelCommand(self))
        self.add_command(clicommands.TestSubjectStateCommand(self))
        self.add_command(clicommands.TestSubjectListCommand(self))
        self.add_command(clicommands.TestSubjectPrepCommand(self))
        self.add_command(clicommands.VendorAddCommand(self))
        self.add_command(clicommands.VendorDelCommand(self))
        self.add_command(clicommands.VendorListCommand(self))
        self.add_command(clicommands.OsAddCommand(self))
        self.add_command(clicommands.OsDelCommand(self))
        self.add_command(clicommands.OsListCommand(self))
        self.scriptname = basename(args[0])
        self.args = args[1:]
        self.run_command()

    def add_command(self, command):
        """Links all command aliases to a command
        """
        for name in command.get_names():
            self.commands[name] = command

    def run_command(self):
        """Runs a command depending on the given arguments
           and does error handling
        """
        if len(self.args) == 0:
            sys.stderr.write("There was no command given.\n")
            self.commands['help'].do_command()
            sys.exit(1)
        elif self.args[0] not in self.commands.keys():
            sys.stderr.write("No such command.\n")
            self.commands['help'].do_command()
            sys.exit(1)
        else:
            command = self.args[0]
            args = self.args[1:]
            try:
                self.commands[command].do_command(args)
            except ValueError, err:
                usage = self.commands['help'].get_command_usage(command)
                sys.stderr.write("%s\n\n%s\n" % (err[0], usage))
                sys.exit(1)


if __name__ == '__main__':
    test = TemareCli(sys.argv)
