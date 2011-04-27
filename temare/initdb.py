#!/usr/bin/env python
# vim: tabstop=4 shiftwidth=4 expandtab smarttab
"""Script to set up and fill a schedule database for debugging
"""
import sqlite3
from config import dbpath


vendors = ((1, "Community"),
           (2, "Microsoft"),
           (3, "Novell"   ),
           (4, "RedHat"   ),
           (5, "Sun"      ))

ostypes = ((1, "Linux"  ),
           (2, "Solaris"),
           (3, "Windows"))

tests = ((1, "CTCS"     , 'run_cerberus',   1, 36000, 28800),
         (2, "kernbench", 'loop_kernbench', 1, 36000, 28800),
         (3, "lmbench"  , 'loop_lmbench',   1, 36000, 28800),
         (4, "lmbench"  , 'loop_lmbench',   2, 36000, 28800),
         (5, "LTP"      , 'run_ltp',        1, 36000, 28800),
         (6, "WinSST"   , 'run_sst.bat',    3, 36000, 28800))

hosts = (( 1, "unicorn",  8192,  4, 0, 0, 1, 1),
         ( 2, "nagult",   8192,  4, 0, 0, 1, 1),
         ( 3, "microbe",  8192,  4, 0, 0, 1, 1),
         ( 4, "selimaga", 4096,  4, 0, 0, 1, 1),
         ( 5, "oracle",   4096,  2, 0, 0, 0, 1),
         ( 6, "pudding",  4096,  2, 0, 0, 1, 1),
         ( 7, "satyr",    4096,  2, 0, 0, 0, 1),
         ( 8, "lemure",   4096,  2, 0, 0, 1, 1),
         ( 9, "azael",    4096,  2, 0, 0, 1, 1),
         (10, "athene",   4096,  2, 0, 0, 1, 1),
         (11, "kobold",   5120,  8, 0, 0, 1, 1),
         (12, "harpy",    6144,  8, 0, 0, 1, 1),
         (13, "incubus",  6144,  8, 0, 0, 1, 1),
         (14, "uruk",     12288, 8, 0, 0, 1, 1))

subjects = ((1, "xen-unstable",    1, 0, 1),
            (2, "xen-unstable",    1, 1, 1),
            (3, "xen-3.3-testing", 1, 0, 1),
            (4, "xen-3.3-testing", 1, 1, 1),
            (5, "xen-3.2-testing", 1, 0, 1),
            (6, "xen-3.2-testing", 1, 1, 1),
            (7, "kvm-unstable",    1, 1, 1))

images = (
    ( 1, "ms_server2008_32b_smp_qcow.img",          "qcow", 2, 3, 0, 0, 1, 1),
    ( 2, "ms_server2008_32b_up_qcow.img",           "qcow", 2, 3, 0, 0, 0, 1),
    ( 3, "ms_server2008_64b_smp_qcow.img",          "qcow", 2, 3, 1, 1, 1, 1),
    ( 4, "ms_server2008_64b_up_qcow.img",           "qcow", 2, 3, 1, 1, 0, 1),
    ( 5, "ms_vista_32b_smp_qcow.img",               "qcow", 2, 3, 0, 0, 1, 1),
    ( 6, "ms_vista_32b_up_qcow.img",                "qcow", 2, 3, 0, 0, 0, 1),
    ( 7, "ms_vista_64b_up_qcow.img",                "qcow", 2, 3, 1, 1, 0, 1),
    ( 8, "ms_win2003_64bit_smp_qcow.img",           "qcow", 2, 3, 1, 1, 1, 1),
    ( 9, "ms_win2003server_ee_sp2_32b_up_qcow.img", "qcow", 2, 3, 0, 0, 0, 1),
    (10, "ms_winxp_pro_sp2_64bit_smp_qcow.img",     "qcow", 2, 3, 1, 1, 1, 1),
    (11, "ms_winxp-sp3_32b_up_qcow.img",            "qcow", 2, 3, 0, 0, 0, 1),
    (12, "opensolaris_2008.11.qcow.img",            "qcow", 5, 2, 1, 1, 1, 0),
    (13, "redhat_rhel3u9_64b_up_qcow.img",          "qcow", 4, 1, 1, 1, 0, 0),
    (14, "redhat_rhel4u7_32b_pae_qcow.img",         "qcow", 4, 1, 0, 1, 1, 1),
    (15, "redhat_rhel4u7_32b_smp_qcow.img",         "qcow", 4, 1, 0, 0, 1, 1),
    (16, "redhat_rhel4u7_32b_up_qcow.img",          "qcow", 4, 1, 0, 0, 0, 1),
    (17, "redhat_rhel4u7_64b_smp_qcow.img",         "qcow", 4, 1, 1, 1, 1, 1),
    (18, "redhat_rhel4u7_64b_up_qcow.img",          "qcow", 4, 1, 1, 1, 0, 1),
    (19, "redhat_rhel5u2_32bpae_smp_up_qcow.img",   "qcow", 4, 1, 0, 1, 1, 1),
    (20, "redhat_rhel5u2_32b_smp_up_qcow.img",      "qcow", 4, 1, 0, 0, 1, 1),
    (21, "redhat_rhel5u2_64b_smp_up_qcow.img",      "qcow", 4, 1, 1, 1, 1, 1),
    (22, "suse_sles10_32bpae_smp_qcow.img",         "qcow", 3, 1, 0, 1, 1, 1),
    (23, "suse_sles10_32b_smp_qcow.img",            "qcow", 3, 1, 0, 0, 1, 1),
    (24, "suse_sles10_32b_up_qcow.img",             "qcow", 3, 1, 0, 0, 0, 1),
    (25, "suse_sles10_64b_smp_qcow.img",            "qcow", 3, 1, 1, 1, 1, 1),
    (26, "suse_sles10_64b_up_qcow.img",             "qcow", 3, 1, 1, 1, 0, 1),
    (27, "suse_sles94_32b_up_qcow.img",             "qcow", 3, 1, 0, 0, 0, 1),
    (28, "suse_suse10_32bpae_smp_qcow.img",         "qcow", 3, 1, 0, 1, 1, 1),
    (29, "suse_suse10_32b_smp_qcow.img",            "qcow", 3, 1, 0, 0, 1, 1),
    (30, "suse_suse10_32b_up_qcow.img",             "qcow", 3, 1, 0, 0, 0, 1),
    (31, "suse_suse10_64b_smp_qcow.img",            "qcow", 3, 1, 1, 1, 1, 1),
    (32, "suse_suse10_64b_up_qcow.img",             "qcow", 3, 1, 1, 1, 0, 1))

connection = sqlite3.connect(dbpath)
cursor = connection.cursor()

cursor.execute('''CREATE TABLE vendor (
                    vendor_id      INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    vendor_name    TEXT UNIQUE)''')
for dataset in vendors:
    cursor.execute('INSERT INTO vendor VALUES (?,?)', dataset)

cursor.execute('''CREATE TABLE os_type (
                    os_type_id     INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    os_type_name   TEXT UNIQUE)''')
for dataset in ostypes:
    cursor.execute('INSERT INTO os_type VALUES (?,?)', dataset)

cursor.execute('''CREATE TABLE test (
                    test_id        INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    test_name      TEXT,
                    test_command   TEXT,
                    os_type_id     INTEGER NOT NULL,
                    timeout        INTEGER DEFAULT 36000,
                    runtime        INTEGER DEFAULT 28800)''')
for dataset in tests:
    cursor.execute('INSERT INTO test VALUES (?,?,?,?,?,?)', dataset)

cursor.execute('''CREATE TABLE host (
                    host_id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    host_name       TEXT UNIQUE,
                    host_memory     INTEGER,
                    host_cores      INTEGER,
                    last_vendor_id  INTEGER DEFAULT 0,
                    last_subject_id INTEGER DEFAULT 0,
                    is_64bit        INTEGER DEFAULT 1,
                    is_enabled      INTEGER DEFAULT 1)''')
for dataset in hosts:
    cursor.execute('INSERT INTO host VALUES (?,?,?,?,?,?,?,?)', dataset)

cursor.execute('''CREATE TABLE subject (
                    subject_id     INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    subject_name   TEXT,
                    subject_prio   INTEGER DEFAULT 100,
                    last_vendor_id INTEGER DEFAULT 0,
                    is_64bit       INTEGER DEFAULT 1,
                    is_enabled     INTEGER DEFAULT 1)''')
for dataset in subjects:
    cursor.execute('INSERT INTO subject VALUES (?,?,?,?,?)', dataset)

cursor.execute('''CREATE TABLE image (
                    image_id       INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    image_name     TEXT UNIQUE,
                    image_format   TEXT,
                    vendor_id      INTEGER NOT NULL,
                    os_type_id     INTEGER NOT NULL,
                    is_64bit       INTEGER DEFAULT 1,
                    is_bigmem      INTEGER DEFAULT 1,
                    is_smp         INTEGER DEFAULT 1,
                    is_enabled     INTEGER DEFAULT 1)''')
for dataset in images:
    cursor.execute('INSERT INTO image VALUES (?,?,?,?,?,?,?,?,?)', dataset)

cursor.execute('''CREATE TABLE host_schedule (
                    schedule_id    INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    host_id        INTEGER NOT NULL,
                    test_id        INTEGER NOT NULL,
                    image_id       INTEGER NOT NULL,
                    is_done        INTEGER DEFAULT 0)''')
cursor.execute('''INSERT INTO host_schedule (host_id, test_id, image_id)
                  SELECT host_id, test_id, image_id
                  FROM host
                  LEFT JOIN image
                  LEFT JOIN test ON test.os_type_id=image.os_type_id''')

cursor.execute('''CREATE TABLE subject_schedule (
                    schedule_id    INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    subject_id     INTEGER NOT NULL,
                    test_id        INTEGER NOT NULL,
                    image_id       INTEGER NOT NULL,
                    is_done        INTEGER DEFAULT 0)''')
cursor.execute('''INSERT INTO subject_schedule (subject_id, test_id, image_id)
                  SELECT subject_id, test_id, image_id
                  FROM subject
                  LEFT JOIN image
                  LEFT JOIN test ON test.os_type_id=image.os_type_id''')

cursor.execute('''CREATE TABLE completion(
                    completion_id  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    subject_id     INTEGER NOT NULL,
                    key            TEXT,
                    value          TEXT)''')

connection.commit()
cursor.close()
