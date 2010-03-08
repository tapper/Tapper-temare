import unittest
import os
os.environ['HARNESS_ACTIVE'] = '1'
from src import preparation
import pprint

class TestPreparation(unittest.TestCase):

    def test_xenhostpreparation(self):
        prep = preparation.SubjectPreparation('bullock')
        precondition = prep.gen_precondition_xen()
        self.assertTrue(precondition['precondition_type'] == 'virt')

    def test_xenhostpreparation_deeply(self):
        prep = preparation.SubjectPreparation('bullock')
        precondition = prep.gen_precondition_xen()
        self.assertTrue(precondition['host']['root']['partition'] == '/dev/sda2')



if __name__ == '__main__':
    unittest.main()

        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(os.environ)
