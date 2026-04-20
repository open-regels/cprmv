#!/bin/sh

# requires pyshacl : to install use: pip install pyshacl
pyshacl -s cprmv.shacl.ttl -i both -m -e cprmv.ttl -f human test.ttl
