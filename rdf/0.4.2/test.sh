#!/bin/sh

echo Testing with basic test file and api output for all 4 implemented methods...
# requires pyshacl : to install use: pip install pyshacl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human test.ttl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testbwb.ttl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testcvdr.ttl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testdmn.ttl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testfmx4.ttl
