#!/bin/sh

echo Testing with basic test file...
# requires pyshacl : to install use: pip install pyshacl
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human test.ttl

echo Testing api all method definitions in the methods subfolder...
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human `ls methods/*/method.ttl`

echo Testing api output for all 4 implemented methods...
echo BWB
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testbwb.ttl
echo CVDR
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testcvdr.ttl
echo DMN13
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testdmn.ttl
echo FMX4
pyshacl -s cprmv.shacl.ttl -i both -e cprmv.ttl -f human testfmx4.ttl
