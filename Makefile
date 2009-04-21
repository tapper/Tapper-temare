SHELL = /bin/bash

.PHONY: all
all:
	@echo "Available targets:"
	@echo "    debugenv  --  Sets up an environment for debugging"
	@echo "    clean     --  Cleans up the environment for debugging"

debug:
	/bin/mkdir -p debug/configs
	/bin/mkdir -p debug/builds/{i386,x86_64}/xen-{3.3,3.2,3.1}-testing
	/bin/mkdir -p debug/builds/{i386,x86_64}/xen-unstable
	cs='12345_abcdef1234567890';					\
	bdate=`date +%Y-%m-%d`;						\
	for d in debug/builds/{i386,x86_64}/xen-*; do			\
		repo=`basename $$d`;					\
		archdir=`dirname $$d`;					\
		arch=`basename $$archdir`;				\
		/bin/touch $$d/$$repo\.$$bdate\.$$cs\.$$arch\.tgz;	\
	done

test-schedule.db: debug
	/bin/sed -i -e 's/^debug = [^\r]*/debug = True/' src/config.py
	src/initdb.py

.PHONY: debugenv
debugenv: test-schedule.db

.PHONY: clean
clean:
	/bin/rm -fr debug
	/bin/rm -f test-schedule.db
	/bin/sed -i -e 's/^debug = [^\r]*/debug = False/' src/config.py
