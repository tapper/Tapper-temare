import unittest
import os
os.environ['HARNESS_ACTIVE'] = '1'
os.system('cp t/orig-db t/test-schedule.db')
from src import preparation
import pprint
import random
import re
random.seed(1)

class TestPreparation(unittest.TestCase):

    def test_xenhostpreparation(self):
        prep = preparation.SubjectPreparation('bullock', 'xen-unstable', 1)
        precondition = prep.gen_precondition_xen()
        self.assertTrue(precondition['precondition_type'] == 'virt')


    def test_xenhostpreparation_deeply(self):
        prep = preparation.SubjectPreparation('bullock', 'xen-unstable', 1)
        precondition = prep.gen_precondition_xen()
        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(precondition)
        self.assertTrue(precondition['host']['root']['partition'] == '/dev/sda2')
        self.assertTrue(precondition['host']['preconditions'][0]['filename'] == \
                            't/misc_files/builds/x86_64/xen-unstable/xen-unstable.2010-03-02.20993_4554b305228a_.x86_64.tgz')
        self.assertTrue(precondition['host']['root']['image'] == \
                            'suse/suse_sles10_sp2_64b_smp_raw.tar.gz')
        self.assertTrue(precondition['host']['testprogram']['execname'] == \
                            '/opt/artemis/bin/metainfo')


    def test_kvmhostpreparation(self):
        prep = preparation.SubjectPreparation('bullock', 'kvm', 1)
        precondition = prep.gen_precondition_kvm()
        self.assertTrue(precondition['precondition_type'] == 'virt')


    def test_kvmhostpreparation_deeply(self):
        prep = preparation.SubjectPreparation('bullock', 'kvm', 1)
        precondition = prep.gen_precondition_kvm()
        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(precondition)
        self.assertTrue(precondition['guests'][0]['root']['arch'] == 'linux32')
        self.assertTrue(precondition['host']['testprogram']['execname'] == \
                            '/opt/artemis/bin/metainfo')
        self.assertTrue(precondition['guests'][0]['config'].has_key('exec'))
        self.assertTrue(precondition['guests'][0]['config']['exec'].startswith('/kvm/images/001-bullock-'))


    def test_autoinstallpreparation(self):
        prep = preparation.SubjectPreparation('bullock', 'autoinstall-rhel6-kvm', 1)
        precondition = prep.gen_precondition_autoinstall()
        self.assertTrue(precondition['precondition_type'] == 'virt')

    def test_autoinstallpreparation_deeply(self):
        prep = preparation.SubjectPreparation('bullock', 'autoinstall-rhel6-kvm', 1)
        precondition = prep.gen_precondition_autoinstall()
        self.assertTrue(precondition['host']['root']['grub_text'] == \
                            '   timeout 2\n\n   title RedHat Testing\n   kernel /tftpboot/stable/kernel/vmlinuz  console=ttyS0,115200 ks=/path/to/ks_file.ks ksdevice=eth0 noapic $ARTEMIS_OPTIONS\n   initrd /tftpboot/stable/initrd/initrd')
        self.assertTrue(re.match('/kvm/images/001-bullock-\d+.sh',precondition['guests'][0]['config']['exec']))



if __name__ == '__main__':
    unittest.main()

        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(os.environ)
