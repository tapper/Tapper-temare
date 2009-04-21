#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Module for database operations to be performed on the schedule database
"""
import sqlite3
import checks
from config import dbpath


def init_database():
    """Sets up a database and creates all needed tables.

    Mainly used for debugging right now.
    See also initdb.py to get a filled database.
    """
    connection = sqlite3.connect(dbpath)
    cursor = connection.cursor()
    statements = [
            '''CREATE TABLE IF NOT EXISTS subject (
                    subject_id      INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    subject_name    TEXT,
                    last_vendor_id  INTEGER DEFAULT 0,
                    is_64bit        INTEGER DEFAULT 1,
                    is_enabled      INTEGER DEFAULT 1)''',
            '''CREATE TABLE IF NOT EXISTS vendor (
                    vendor_id       INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    vendor_name     TEXT UNIQUE)''',
            '''CREATE TABLE IF NOT EXISTS os_type (
                    os_type_id      INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    os_type_name    TEXT UNIQUE)''',
            '''CREATE TABLE IF NOT EXISTS test (
                    test_id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    test_name       TEXT,
                    test_command    TEXT,
                    os_type_id      INTEGER NOT NULL)''',
            '''CREATE TABLE IF NOT EXISTS host (
                    host_id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    host_name       TEXT UNIQUE,
                    host_memory     INTEGER,
                    host_cores      INTEGER,
                    last_vendor_id  INTEGER DEFAULT 0,
                    last_subject_id INTEGER DEFAULT 0,
                    is_64bit        INTEGER DEFAULT 1,
                    is_enabled      INTEGER DEFAULT 1)''',
            '''CREATE TABLE IF NOT EXISTS image (
                    image_id        INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    image_name      TEXT UNIQUE,
                    image_format    TEXT,
                    vendor_id       INTEGER NOT NULL,
                    os_type_id      INTEGER NOT NULL,
                    is_64bit        INTEGER DEFAULT 1,
                    is_bigmem       INTEGER DEFAULT 1,
                    is_smp          INTEGER DEFAULT 1,
                    is_enabled      INTEGER DEFAULT 1)''',
            '''CREATE TABLE IF NOT EXISTS host_schedule (
                    schedule_id     INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    host_id         INTEGER NOT NULL,
                    test_id         INTEGER NOT NULL,
                    image_id        INTEGER NOT NULL,
                    is_done         INTEGER DEFAULT 0)''',
            '''CREATE TABLE IF NOT EXISTS subject_schedule (
                    schedule_id     INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    subject_id      INTEGER NOT NULL,
                    test_id         INTEGER NOT NULL,
                    image_id        INTEGER NOT NULL,
                    is_done         INTEGER DEFAULT 0)''']
    try:
        for stmt in statements:
            cursor.execute(stmt)
        connection.commit()
    except sqlite3.Error, err:
        raise ValueError(err.args[0])
    finally:
        cursor.close()
        connection.close()


def fetchassoc(cursor):
    """Return dictionaries for each resulting row of a database query.

    Arguments:
        cursor -- A database cursor object having query result sets
    Returns:
        A tuple of dictionaries containing pairs of column name and value
    """
    retval = ()
    row = cursor.fetchone()
    while row:
        entry = {}
        count = 0
        for description in cursor.description:
            colname = description[0]
            value = row[count]
            entry[colname] = value
            count += 1
        retval += (entry, )
        row = cursor.fetchone()
    return retval


class DatabaseEntity:
    """Base class for database interaction objects
    """

    def __init__(self):
        init_database()
        self.connection = sqlite3.connect(dbpath)
        self.cursor = self.connection.cursor()

    def add(self, args):
        """Add an item to the database
        """
        raise NotImplementedError

    def delete(self, args):
        """Remove an item and all its dependencies from the database
        """
        raise NotImplementedError

    # Might be added later...
    #
    #def modify(self):
    #    """Modify the properties of an item
    #    """
    #    raise NotImplementedError

    def state(self, args):
        """Set the state of an item to enabled or disabled
        """
        pass

    def list(self):
        """Return a list of all items
        """
        raise NotImplementedError


class Hosts(DatabaseEntity):
    """Class for database operations on host entries
    """

    def add(self, args):
        """Add a new host to the database.

        Arguments:
            hostname -- Name of the host system
            memory   -- Amount of memory available on the host system
            cores    -- Amount of CPU cores available on the host system
            bitness  -- Bitness of the host OS (0 = 32-bit, 1 = 64-bit)
        """
        checks.chk_arg_count(args, 4)
        hostname, memory, cores, bitness = args
        hostname = checks.chk_hostname(hostname)
        memory = checks.chk_memory(memory)
        cores = checks.chk_cores(cores)
        bitness = checks.chk_bitness(bitness)
        try:
            self.cursor.execute('''
                    INSERT INTO host
                    (host_name, host_memory, host_cores, is_64bit)
                    VALUES (?,?,?,?)''', (hostname, memory, cores, bitness))
        except sqlite3.IntegrityError:
            raise ValueError('Host already exists.')
        self.cursor.execute('''
                INSERT INTO host_schedule (host_id, test_id, image_id)
                SELECT host_id, test_id, image_id
                FROM host LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE host_name=? AND test_id NOT NULL
                AND image_id NOT NULL''', (hostname, ))
        self.connection.commit()

    def delete(self, args):
        """Remove a host from the database.

        This will also remove all schedule entries for this host.
        Arguments:
            hostname -- Name of the host system
        """
        checks.chk_arg_count(args, 1)
        hostname, = args
        hostname = checks.chk_hostname(hostname)
        self.cursor.execute('''
                SELECT host_id FROM host WHERE host_name=?''', (hostname, ))
        hostid = self.cursor.fetchone()
        if hostid == None:
            raise ValueError('No such host.')
        self.cursor.execute('''
                DELETE FROM host_schedule WHERE host_id=?''', hostid)
        self.cursor.execute('DELETE FROM host WHERE host_id=?', hostid)
        self.connection.commit()

    def state(self, args):
        """Set the state of a host to enabled or disabled

        Arguments: A list with following items in that order
            * Name of the host
            * State of the host as specified in checks.chk_state()
        """
        checks.chk_arg_count(args, 2)
        hostname, state = args
        hostname = checks.chk_hostname(hostname)
        state = checks.chk_state(state)
        self.cursor.execute('''
                SELECT * FROM host WHERE host_name=?''', (hostname, ))
        if self.cursor.fetchone() == None:
            raise ValueError('No such host.')
        self.cursor.execute('''UPDATE host SET is_enabled=?
                WHERE host_name=?''', (state, hostname))
        self.connection.commit()

    def list(self):
        """Return a list of all hosts and their properties.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT host_name, host_memory, host_cores,
                       is_64bit, is_enabled
                FROM host ORDER BY host_name''')
        return fetchassoc(self.cursor)


class Images(DatabaseEntity):
    """Class for database operations on guest image entries
    """

    def add(self, args):
        """Add a new guest image to the database.

        Arguments:
            imagename -- Filename of the guest image
            format    -- Format of the guest image
            vendor    -- Vendor or distributor name of the guests OS
            ostype    -- Operating system type of the guest image
            bitness   -- 1 for 64-bit guests, 0 for 32-bit guests
            bigmem    -- 1 for 32-bit PAE and 64-bit guests, otherwise 0
            smp       -- 1 for SMP guests, otherwise 0
        """
        checks.chk_arg_count(args, 7)
        imagename, format, vendor, ostype, bitness, bigmem, smp = args
        imagename = checks.chk_imagename(imagename)
        format = checks.chk_imageformat(format)
        vendor = checks.chk_vendor(vendor)
        ostype = checks.chk_ostype(ostype)
        bitness = checks.chk_bitness(bitness)
        bigmem = checks.chk_bigmem(bigmem)
        smp = checks.chk_smp(smp)
        if bitness == 1:
            bigmem = 1
        self.cursor.execute('''
                SELECT vendor_id FROM vendor
                WHERE vendor_name=?''', (vendor, ))
        row = self.cursor.fetchone()
        if row == None:
            raise ValueError('No such vendor.')
        vendorid = row[0]
        self.cursor.execute('''
                SELECT os_type_id FROM os_type
                WHERE os_type_name=?''', (ostype, ))
        row = self.cursor.fetchone()
        if row == None:
            raise ValueError('No such OS type.')
        ostypeid = row[0]
        try:
            self.cursor.execute('''
                    INSERT INTO image
                    (image_name, image_format, vendor_id, os_type_id,
                     is_64bit, is_bigmem, is_smp, is_enabled)
                    VALUES (?,?,?,?,?,?,?,?)''',
                    (imagename, format, vendorid, ostypeid,
                    bitness, bigmem, smp, 1))
        except sqlite3.IntegrityError:
            raise ValueError('Image already exists.')
        self.cursor.execute('''
                INSERT INTO host_schedule (host_id, test_id, image_id)
                SELECT host_id, test_id, image_id
                FROM host LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE image_name=? AND host_id NOT NULL
                AND test_id NOT NULL''', (imagename, ))
        self.cursor.execute('''
                INSERT INTO subject_schedule (subject_id, test_id, image_id)
                SELECT subject_id, test_id, image_id
                FROM subject LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE image_name=? AND subject_id NOT NULL
                AND test_id NOT NULL''', (imagename, ))
        self.connection.commit()

    def delete(self, args):
        """Remove a guest image from the database.

        This will also remove all schedule entries for this guest image.
        Arguments:
            imagename -- Filename of the guest image
        """
        checks.chk_arg_count(args, 1)
        imagename, = args
        imagename = checks.chk_imagename(imagename)
        self.cursor.execute('''
                SELECT image_id FROM image
                WHERE image_name=?''', (imagename, ))
        imageid = self.cursor.fetchone()
        if imageid == None:
            raise ValueError('No such image.')
        self.cursor.execute('''
                DELETE FROM host_schedule WHERE image_id=?''', imageid)
        self.cursor.execute('''
                DELETE FROM subject_schedule WHERE image_id=?''', imageid)
        self.cursor.execute('DELETE FROM image WHERE image_id=?', imageid)
        self.connection.commit()

    def state(self, args):
        """Set the state of a guest image to enabled or disabled

        Arguments: A list with following items in that order
            * Filename of the guest image
            * State of the guest image as specified in checks.chk_state()
        """
        checks.chk_arg_count(args, 2)
        imagename, state = args
        imagename = checks.chk_imagename(imagename)
        state = checks.chk_state(state)
        self.cursor.execute('''
                SELECT * FROM image WHERE image_name=?''', (imagename, ))
        if self.cursor.fetchone() == None:
            raise ValueError('No such guest image.')
        self.cursor.execute('''UPDATE image SET is_enabled=?
                WHERE image_name=?''', (state, imagename))
        self.connection.commit()

    def list(self):
        """Return a list of all guest images and their properties.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT image_name, image_format, vendor_name, os_type_name,
                       is_64bit, is_bigmem, is_smp, is_enabled
                FROM image
                LEFT JOIN os_type ON image.os_type_id=os_type.os_type_id
                LEFT JOIN vendor ON image.vendor_id=vendor.vendor_id
                ORDER BY image_name''')
        return fetchassoc(self.cursor)


class OsTypes(DatabaseEntity):
    """Class for database operations on OS type entries
    """

    def add(self, args):
        """Add a new operating system type to the database.

        Arguments:
            ostype -- Name of the operating system type to be added
        """
        checks.chk_arg_count(args, 1)
        ostype, = args
        ostype = checks.chk_ostype(ostype)
        try:
            self.cursor.execute('''
                    INSERT INTO os_type
                    (os_type_name) VALUES (?)''', (ostype, ))
            self.connection.commit()
        except sqlite3.IntegrityError:
            raise ValueError('OS type already exists.')

    def delete(self, args):
        """Remove an operating system type from the database.

        This will also remove all image files, tests, and
        schedule entries linked to this operating system type.
        Arguments:
            ostype -- Name of the operating system type to be removed
        """
        checks.chk_arg_count(args, 1)
        ostype, = args
        ostype = checks.chk_ostype(ostype)
        self.cursor.execute('''
                SELECT os_type_id FROM os_type
                WHERE os_type_name=?''', (ostype, ))
        ostypeid = self.cursor.fetchone()
        if ostypeid == None:
            raise ValueError('No such OS type.')
        self.cursor.execute('''
                SELECT image_id FROM image WHERE os_type_id=?''', ostypeid)
        result = self.cursor.fetchall()
        if result != None:
            imagelist = ()
            for imageid in result:
                imagelist += imageid
            wildcards = ','.join(['?'] * len(imagelist))
            self.cursor.execute('''
                    DELETE FROM host_schedule
                    WHERE image_id IN (%s)''' % wildcards, imagelist)
            self.cursor.execute('''
                    DELETE FROM subject_schedule
                    WHERE image_id IN (%s)''' % wildcards, imagelist)
            self.cursor.execute('''
                    DELETE FROM image WHERE os_type_id=?''', ostypeid)
        self.cursor.execute('DELETE FROM test WHERE os_type_id=?', ostypeid)
        self.cursor.execute('DELETE FROM os_type WHERE os_type_id=?', ostypeid)
        self.connection.commit()

    def list(self):
        """Return a list of all operating system types.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT os_type_name FROM os_type ORDER BY os_type_name''')
        return fetchassoc(self.cursor)


class Tests(DatabaseEntity):
    """Class for database operations on test program entries
    """

    def add(self, args):
        """Add a new test program for a specific operating system type
        to the database.

        Arguments:
            testname    -- Name of the test program
            ostype      -- Name of the OS the test program is meant to run on
            testcommand -- Command to start the test program
        """
        checks.chk_arg_count(args, 3)
        testname, ostype, testcommand = args
        testname = checks.chk_testname(testname)
        ostype = checks.chk_ostype(ostype)
        testcommand = checks.chk_testcommand(testcommand)
        self.cursor.execute('''
                SELECT os_type_id FROM os_type
                WHERE os_type_name=?''', (ostype, ))
        row = self.cursor.fetchone()
        if row == None:
            raise ValueError('No such OS type.')
        ostypeid = row[0]
        self.cursor.execute('''
                SELECT * FROM test
                WHERE test_name=? AND os_type_id=?''', (testname, ostypeid))
        if self.cursor.fetchone() != None:
            raise ValueError('Test already exists.')
        self.cursor.execute('''
                INSERT INTO test (test_name, os_type_id, test_command)
                VALUES (?,?,?)''', (testname, ostypeid, testcommand))
        self.cursor.execute('''
                INSERT INTO host_schedule (host_id, test_id, image_id)
                SELECT host_id, test_id, image_id
                FROM host LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE test_name=? AND test.os_type_id=?
                AND host_id NOT NULL AND image_id NOT NULL''',
                (testname, ostypeid))
        self.cursor.execute('''
                INSERT INTO subject_schedule (subject_id, test_id, image_id)
                SELECT subject_id, test_id, image_id
                FROM subject LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE test_name=? and test.os_type_id=?
                AND subject_id NOT NULL AND image_id NOT NULL''',
                (testname, ostypeid))
        self.connection.commit()

    def delete(self, args):
        """Remove a test program from the database.

        This will also remove all schedule entries for this test program.
        Arguments:
            testname    -- Name of the test program
            ostype      -- Name of the OS the test program is meant to run on
        """
        checks.chk_arg_count(args, 2)
        testname, ostype = args
        testname = checks.chk_testname(testname)
        ostype = checks.chk_ostype(ostype)
        self.cursor.execute('''
                SELECT test_id FROM test
                LEFT JOIN os_type ON os_type.os_type_id=test.os_type_id
                WHERE test_name=? AND os_type_name=?''', (testname, ostype))
        testid = self.cursor.fetchone()
        if testid == None:
            raise ValueError('No such test.')
        self.cursor.execute('''
                DELETE FROM host_schedule WHERE test_id=?''', testid)
        self.cursor.execute('''
                DELETE FROM subject_schedule WHERE test_id=?''', testid)
        self.cursor.execute('DELETE FROM test WHERE test_id=?', testid)
        self.connection.commit()

    def list(self):
        """Return a list of all test programs.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT test_name, os_type_name, test_command FROM test
                LEFT JOIN os_type ON os_type.os_type_id=test.os_type_id
                ORDER BY test_name''')
        return fetchassoc(self.cursor)


class TestSubjects(DatabaseEntity):
    """Class for database operations on test subjects
    """

    def add(self, args):
        """Add a new test subject to the database.

        Arguments:
            subject  -- Name of the test subject
            bitness  -- Bitness of the test subject (0 = 32-bit, 1 = 64-bit)
        """
        checks.chk_arg_count(args, 2)
        subject, bitness = args
        subject = checks.chk_subject(subject)
        bitness = checks.chk_bitness(bitness)
        self.cursor.execute('''
                SELECT * FROM subject
                WHERE subject_name=? AND is_64bit=?''', (subject, bitness))
        if self.cursor.fetchone() != None:
            raise ValueError('Test subject already exists.')
        self.cursor.execute('''
                INSERT INTO subject
                (subject_name, last_vendor_id, is_64bit, is_enabled)
                VALUES (?,?,?,?)''',
                (subject, 0, bitness, 1))
        self.cursor.execute('''
                INSERT INTO subject_schedule (subject_id, test_id, image_id)
                SELECT subject_id, test_id, image_id
                FROM subject LEFT JOIN image
                LEFT JOIN test ON test.os_type_id=image.os_type_id
                WHERE subject_name=? AND test_id NOT NULL
                AND image_id NOT NULL''', (subject, ))
        self.connection.commit()

    def delete(self, args):
        """Remove a test subject from the database.

        This will also remove all schedule entries for this subject.
        Arguments:
            subject -- Name of the test subject
        """
        checks.chk_arg_count(args, 2)
        subject, bitness = args
        subject = checks.chk_subject(subject)
        bitness = checks.chk_bitness(bitness)
        self.cursor.execute('''
                SELECT subject_id FROM subject
                WHERE subject_name=? AND is_64bit=?''',
                (subject, bitness))
        subjectid = self.cursor.fetchone()
        if subjectid == None:
            raise ValueError('No such test subject.')
        self.cursor.execute('''
                DELETE FROM subject_schedule WHERE subject_id=?''', subjectid)
        self.cursor.execute('''
                DELETE FROM subject WHERE subject_id=?''', subjectid)
        self.connection.commit()

    def state(self, args):
        """Set the state of a test subject to enabled or disabled

        Arguments: A list with following items in that order
            * Name of the test subject
            * State of the test subject as specified in checks.chk_state()
        """
        checks.chk_arg_count(args, 3)
        subject, bitness, state = args
        subject = checks.chk_subject(subject)
        bitness = checks.chk_bitness(bitness)
        state = checks.chk_state(state)
        self.cursor.execute('''
                SELECT * FROM subject WHERE subject_name=? AND is_64bit=?''',
                (subject, bitness))
        if self.cursor.fetchone() == None:
            raise ValueError('No such test subject.')
        self.cursor.execute('''
                UPDATE subject SET is_enabled=?
                WHERE subject_name=? AND is_64bit=?''',
                (state, subject, bitness))
        self.connection.commit()

    def list(self):
        """Return a list of all test subjects and their properties.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT subject_name, is_64bit, is_enabled
                FROM subject ORDER BY subject_name''')
        return fetchassoc(self.cursor)


class Vendors(DatabaseEntity):
    """Class for database operations on vendor entries
    """

    def add(self, args):
        """Add a new vendor entry to the database.

        Arguments:
            vendor -- Name of the vendor to be added
        """
        checks.chk_arg_count(args, 1)
        vendor, = args
        vendor = checks.chk_vendor(vendor)
        try:
            self.cursor.execute('''
                    INSERT INTO vendor (vendor_name) VALUES (?)''',
                    (vendor, ))
            self.connection.commit()
        except sqlite3.IntegrityError:
            raise ValueError('Vendor already exists.')

    def delete(self, args):
        """Remove a vendor entry from the database.

        This will also remove all image files and schedule entries
        linked to this vendor.
        Arguments:
            vendor -- Name of the vendor to be removed
        """
        checks.chk_arg_count(args, 1)
        vendor, = args
        vendor = checks.chk_vendor(vendor)
        self.cursor.execute('''
                SELECT vendor_id FROM vendor WHERE vendor_name=?''',
                (vendor, ))
        vendorid = self.cursor.fetchone()
        if vendorid == None:
            raise ValueError('No such vendor.')
        self.cursor.execute('''
                SELECT image_id FROM image WHERE vendor_id=?''', vendorid)
        result = self.cursor.fetchall()
        if result != None:
            imagelist = ()
            for imageid in result:
                imagelist += imageid
            wildcards = ','.join(['?'] * len(imagelist))
            self.cursor.execute('''
                    DELETE FROM host_schedule
                    WHERE image_id IN (%s)''' % wildcards, imagelist)
            self.cursor.execute('''
                    DELETE FROM subject_schedule
                    WHERE image_id IN (%s)''' % wildcards, imagelist)
            self.cursor.execute('''
                    DELETE FROM image WHERE vendor_id=?''', vendorid)
        self.cursor.execute('DELETE FROM vendor WHERE vendor_id=?', vendorid)
        self.connection.commit()

    def list(self):
        """Return a list of all vendors.

        Returns:
            A tuple of dictionaries containing pairs of column name and value
        """
        self.cursor.execute('''
                SELECT vendor_name FROM vendor ORDER BY vendor_name''')
        return fetchassoc(self.cursor)


if __name__ == "__main__":
    pass
