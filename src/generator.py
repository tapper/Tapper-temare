#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Module to generate guest configurations for a test run
"""
import sqlite3
import checks
import random
from socket import gethostbyname
from config import dbpath


class TestRunGenerator():
    """Class to generate guest configurations for a test run depending on
    system resources and scheduled guest / test combinations

    Arguments:
        hostname -- Name of the host system
        auto     -- Perform test subject rotation or choose a specific one
                    (optional, anything else than False enables it)
        subject  -- Specific test subject to be chosen (optional)
        bitness  -- Bitness of the specific test subject
                    (only required if test subject is specified)

    Provided information:
        TestRunGenerator.host
                Dictionary with the following items:
        'id'            -- Database ID of the host           (integer)
        'name'          -- Hostname                          (string)
        'ip'            -- IP address of the host            (string)

        TestRunGenerator.subject
                Dictionary with the following items:
        'id'            -- Database ID of the test subject   (integer)
        'name'          -- Name of the test subject          (string)
        'bitness'       -- Bitness of the test subject       (0|1)

        TestRunGenerator.tests
                List of dictionaries with the following items:
        'id'            -- Database ID of the schedule entry (integer)
        'runid'         -- Consecutive numbering of the test (integer)
        'vnc'           -- VNC and network iface numbering   (integer)
        'macaddr'       -- MAC address of the guest NIC      (string)
        'image'         -- Guest image name                  (string)
        'format'        -- Guest image format                (raw|qcow|qcow2)
        'test'          -- Name of the test program          (string)
        'testcommand'   -- Test program command              (string)
        'bitness'       -- Bitness of the guest              (0|1)
        'bigmem'        -- Capability to address > 4GB       (0|1)
        'smp'           -- SMP capability of the guest       (0|1)
        'cores'         -- Number of VCPUs                   (integer)
        'memory'        -- Memory                            (integer)
        'shadowmem'     -- Shadow memory                     (integer)
        'hap'           -- Nested paging enabled             (0|1)

    Methods:
        TestRunGenerator.do_finalize()
                Mark all tests used in the testrun as done
    """

    def __init__(self, hostname, auto=False, subject=False, bitness=False):
        self.host = {'id': None, 'name': None, 'ip': None}
        self.subject = {'id': None, 'name': None, 'bitness': None}
        self.resources = \
                {'memory': 0, 'cores': 0, 'bitness': 0, 'lastvendor': 0}
        self.tests = []
        self.connection = sqlite3.connect(dbpath)
        self.cursor = self.connection.cursor()
        self.get_host_info(hostname)
        if auto == False:
            self.schedule = 'host'
        else:
            self.schedule = 'subject'
            self.get_subject_info(subject, bitness)
        self.gen_tests()

    def get_host_info(self, hostname):
        """Fetch values for the host ID, available memory and cores,
        the bitness of the virt system installed on the host,
        the vendor ID of the last guest running on the host

        Arguments:
            hostname -- Name of the host system
        """
        hostname = checks.chk_hostname(hostname)
        self.cursor.execute('''
                SELECT host_id, host_memory, host_cores, last_vendor_id,
                       last_subject_id, is_64bit, is_enabled
                FROM host WHERE host_name=?''', (hostname, ))
        result = self.cursor.fetchone()
        if result == None:
            raise ValueError('No such host.')
        self.host['name'] = hostname
        self.host['ip'] = gethostbyname(hostname)
        self.host['id'], self.resources['memory'], self.resources['cores'], \
                self.resources['lastvendor'], self.resources['lastsubject'], \
                self.resources['bitness'], state = result
        self.resources['memory'] -= 1024
        self.resources['cores'] += 1
        if state != 1:
            raise ValueError('The chosen host is currently disabled.')

    def get_subject_info(self, subject, bitness):
        """Find the next test subject to run on a host and fetch values for
        its ID, bitness and state, and the vendor ID of the last guest
        running on the test subject
        """
        if subject == False and bitness == False:
            self.cursor.execute('''
                    SELECT subject_schedule.subject_id, subject_name,
                        last_vendor_id, is_64bit
                    FROM subject_schedule
                    LEFT JOIN subject ON
                        subject_schedule.subject_id=subject.subject_id
                    WHERE subject_schedule.subject_id>? AND is_enabled=1
                    ORDER BY subject_schedule.subject_id LIMIT 1''',
                    (self.resources['lastsubject'], ))
            result = self.cursor.fetchone()
            if result == None:
                self.cursor.execute('''
                        SELECT subject_schedule.subject_id, subject_name,
                            last_vendor_id, is_64bit
                        FROM subject_schedule
                        LEFT JOIN subject ON
                            subject_schedule.subject_id=subject.subject_id
                        WHERE is_enabled=1
                        ORDER BY subject_schedule.subject_id LIMIT 1''')
                result = self.cursor.fetchone()
                if result == None:
                    raise ValueError('Nothing to do.')
        elif subject != False and bitness in (0,1):
            self.cursor.execute('''
                    SELECT subject_schedule.subject_id, subject_name,
                        last_vendor_id, is_64bit
                    FROM subject_schedule
                    LEFT JOIN subject ON
                        subject_schedule.subject_id=subject.subject_id
                    WHERE is_enabled=1 AND subject_name=? AND is_64bit=?''',
                    (subject, bitness))
            result = self.cursor.fetchone()
            if result == None:
                raise ValueError('No such test subject.')
        else:
            raise ValueError('Test subject or bitness not specified.')
        self.subject['id'],                     \
                self.subject['name'],           \
                self.resources['lastvendor'],   \
                self.resources['bitness'] = result
        self.subject['bitness'] = self.resources['bitness']

    def get_vendor(self):
        """Find the next vendor with possible guest images from the schedule

        Check for the bitness and exclude images already scheduled for the
        current test run. Check if there are still tests to be done for
        the vendor. If there are still tests to be done but only for
        images wich are already scheduled for the current test run, unlock
        a single random test from the already done ones. If all tests are
        done reset the is_done flags of all tests.
        Update last_vendor_id with the determined vendor.

        @return: vendor ID or 0 on failure
        """
        # Gather all bits to construct different database queries
        idvalue = (self.subject['id'], )
        imagevalue = ()
        imagecond = ''
        if self.schedule == 'host':
            idvalue = (self.host['id'], )
        if len(self.tests) != 0:
            imagevalue = tuple([test['image'] for test in self.tests])
            wildcards = ','.join(['?'] * len(imagevalue))
            imagecond = 'AND image_name NOT IN (%s)' % (wildcards, )
        query = '''
                SELECT vendor_id FROM %s_schedule
                LEFT JOIN image ON %s_schedule.image_id=image.image_id
                LEFT JOIN %s ON %s_schedule.%s_id=%s.%s_id
                WHERE %s.is_64bit>=image.is_64bit
                AND image.is_enabled=1
                AND %s_schedule.%s_id=? %s %s
                ORDER BY vendor_id LIMIT 1'''
        # Try to find a vendor
        config = ((self.schedule, ) * 10) + (imagecond, 'AND vendor_id>?')
        values = idvalue + imagevalue + (self.resources['lastvendor'], )
        self.cursor.execute(query % config, values)
        result = self.cursor.fetchone()
        if result == None:
            config = ((self.schedule, ) * 10) + (imagecond, '')
            self.cursor.execute(query % config, (idvalue + imagevalue))
            result = self.cursor.fetchone()
            if result == None:
                return 0
        vendor = result[0]
        # Check is_done flags
        query = '''
                SELECT schedule_id FROM %s_schedule
                LEFT JOIN image ON %s_schedule.image_id=image.image_id
                LEFT JOIN %s ON %s_schedule.%s_id=%s.%s_id
                WHERE %s.is_64bit>=image.is_64bit
                AND image.is_enabled=1
                AND %s_schedule.%s_id=?
                AND %s_schedule.is_done=?
                AND vendor_id=? %s'''
        config = ((self.schedule, ) * 11) + (imagecond, )
        values = idvalue + (0, vendor) + imagevalue
        self.cursor.execute(query % config, values)
        if self.cursor.fetchone() == None:
            # Nothing to be done. But probably still something to do
            # for images already used in the current test run
            config = ((self.schedule, ) * 11) + ('', )
            self.cursor.execute(query % config, (idvalue + (0, vendor)))
            if self.cursor.fetchone() != None:
                # There are still some tests to do, but the image
                # is already used in this test run. Unlock a random
                # test from the done ones.
                config = ((self.schedule, ) * 11) + (imagecond, )
                values = idvalue + (1, vendor) + imagevalue
                self.cursor.execute(query % config, values)
                result = random.choice(self.cursor.fetchall())
                query = 'UPDATE %s_schedule SET is_done=0 WHERE schedule_id=?'
                self.cursor.execute(query % (self.schedule, ), (result[0], ))
                self.connection.commit()
            else:
                # All tests done. Reset all is_done flags.
                self.cursor.execute(query % config, (idvalue + (1, vendor)))
                result = self.cursor.fetchall()
                testval = tuple([test[0] for test in result])
                wildcards = ','.join(['?'] * len(testval))
                config = (self.schedule, wildcards)
                query = '''UPDATE %s_schedule
                        SET is_done=0 WHERE schedule_id IN (%s)'''
                self.cursor.execute(query % config, testval)
                self.connection.commit()
        # Update last_vendor_id
        query = 'UPDATE %s SET last_vendor_id=? WHERE %s_id=?'
        config = (self.schedule, ) * 2
        self.cursor.execute(query % config, ((vendor, ) + idvalue))
        self.connection.commit()
        self.resources['lastvendor'] = vendor
        return vendor

    def do_weighing(self, smallup, smallsmp, bigup, bigsmp):
        """Pick a test most suitable for the available resources
        """
        if self.resources['memory'] > 4096 and len(bigup + bigsmp) != 0:
            if self.resources['cores'] > 1 and len(bigsmp) != 0:
                # select random test from bigsmp, do random cores/mem
                testlist = bigsmp
            elif self.resources['cores'] == 1 and len(bigup) != 0:
                # select random test from bigup, do random cores/mem
                testlist = bigup
            else:
                # select random test from bigup+bigsmp, do random cores/mem
                testlist = bigup + bigsmp
        elif self.resources['cores'] > 1 and len(smallsmp) != 0:
            # select random test from smallsmp, do random cores/mem
            testlist = smallsmp
        elif self.resources['cores'] > 1 and len(smallup) != 0:
            # select random test from smallup, do random cores/mem
            testlist = smallup
        elif self.resources['cores'] > 1 and len(bigsmp) != 0:
            # select random test from bigsmp, do random cores/mem
            testlist = bigsmp
        elif self.resources['cores'] == 1 and len(smallup) != 0:
            # select random test from smallup, do random cores/mem
            testlist = smallup
        elif self.resources['cores'] == 1 and len(bigup) != 0:
            # select random test from bigup, do random cores/mem
            testlist = bigup
        elif self.resources['cores'] == 1 and len(smallsmp) != 0:
            # select random test from smallsmp, do random cores/mem
            testlist = smallsmp
        else:
            # select random test, do random cores/mem
            testlist = smallup + smallsmp + bigup + bigsmp
        return random.choice(testlist)

    def get_test(self):
        """Fetch all possible tests and return a test most suitable
        for the available resources
        """
        # Gather all bits to construct different database queries
        vendor = self.get_vendor()
        if vendor == 0:
            return None
        idvalue = (self.subject['id'], )
        imagevalue = ()
        imagecond = ''
        if self.schedule == 'host':
            idvalue = (self.host['id'], )
        if len(self.tests) != 0:
            imagevalue = tuple([test['image'] for test in self.tests])
            wildcards = ','.join(['?'] * len(imagevalue))
            imagecond = 'AND image_name NOT IN (%s)' % (wildcards, )
        query = '''
                SELECT schedule_id, image_name, image_format, test_name,
                    test_command, is_bigmem, is_smp, image.is_64bit
                FROM %s_schedule
                LEFT JOIN image ON %s_schedule.image_id=image.image_id
                LEFT JOIN test ON %s_schedule.test_id=test.test_id
                LEFT JOIN %s ON %s_schedule.%s_id=%s.%s_id
                WHERE %s.is_64bit>=image.is_64bit
                AND image.is_enabled=1
                AND is_done=0
                AND %s_schedule.%s_id=?
                AND vendor_id=?
                %s'''
        smallup = smallsmp = bigup = bigsmp = []
        self.cursor.execute(
                query % (((self.schedule, ) * 11) + (imagecond, )),
                (idvalue + (vendor, ) + imagevalue))
        row = self.cursor.fetchone()
        while row != None:
            if row[5] == 0 and row[6] == 0:
                smallup.append(row)
            elif row[5] == 0 and row[6] == 1:
                smallsmp.append(row)
            elif row[5] == 1 and row[6] == 0:
                bigup.append(row)
            elif row[5] == 1 and row[6] == 1:
                bigsmp.append(row)
            row = self.cursor.fetchone()
        return dict(zip(
                ('id', 'image', 'format', 'test',
                        'testcommand', 'bigmem', 'smp', 'bitness'),
                self.do_weighing(smallup, smallsmp, bigup, bigsmp)))

    def get_test_config(self, test):
        """Figure out the configuration for a single test

        @return: dict with items 'cores', 'memory', 'shadowmem', and 'hap'
        """
        if self.resources['cores'] == 1 or test['smp'] == 0:
            cores = 1
        else:
            cores = random.randint(2, self.resources['cores'])
        hap = 1
        if self.resources['memory'] > 4096 and test['bigmem'] == 1:
            memory = random.randrange(
                    4096, self.resources['memory'] + 256, 256)
        elif self.resources['memory'] > 4096:
            memory = random.randrange(1024, 4096 + 256, 256)
        else:
            memory = random.randrange(
                    1024, self.resources['memory'] + 256, 256)
        if memory > 3840 and self.resources['bitness'] == 0:
            hap = 0
        shadowmem = int(round(memory * 10 / 1024))
        self.resources['cores'] -= cores
        self.resources['memory'] -= memory
        return {'cores': cores, 'memory': memory,
                'shadowmem': shadowmem, 'hap': hap }

    def gen_macaddr(self, guestid):
        """Generate MAC address for guest NIC

        Generate a MAC address for a guests NIC which is unique
        enough for our environment. Takes the last two digits of the
        virtualization hosts IP and the consecutive number of the guest to
        create the MAC address:
            52:54:00:{host_ip_digit}:{host_ip_digit}:{guest_id}
        """
        digits = self.host['ip'].split('.')[2:4]
        digits.append(guestid)
        digits = tuple([int(digit) for digit in digits])
        return '52:54:00:%02X:%02X:%02X' % digits

    def gen_tests(self):
        """Generate a single test and its configuration
        """
        count = 0
        while self.resources['memory'] >= 1024 and self.resources['cores'] > 0:
            test = self.get_test()
            if test == None and len(self.tests) == 0:
                raise ValueError('Nothing to do.')
            elif test == None:
                break
            test.update(self.get_test_config(test))
            test['vnc'] = count
            test['runid'] = count + 1
            test['macaddr'] = self.gen_macaddr(count + 1)
            test['format'] = checks.chk_imageformat(test['format'])
            test['image'] = checks.chk_imagename(test['image'])
            test['test'] = checks.chk_testname(test['test'])
            test['testcommand'] = checks.chk_testcommand(test['testcommand'])
            self.tests.append(test)
            count += 1

    def do_finalize(self):
        """Set is_done flags for all tests used in the testrun

        This method must be called when all preparation steps succeeded.
        It also resets the TestRunGenerator.tests attribute.
        """
        testids = tuple([test['id'] for test in self.tests])
        wildcards = ','.join(['?'] * len(testids))
        query = 'UPDATE %s_schedule SET is_done=1 WHERE schedule_id IN (%s)'
        self.cursor.execute(query % (self.schedule, wildcards), testids)
        if self.schedule == 'subject':
            query = 'UPDATE host SET last_subject_id=? WHERE host_id=?'
            self.cursor.execute(query, (self.subject['id'], self.host['id']))
        self.connection.commit()
        self.tests = []


if __name__ == '__main__':
    pass
