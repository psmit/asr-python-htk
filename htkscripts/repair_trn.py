#!/usr/bin/env python2.6

from optparse import OptionParser
import os

usage = "usage: %prog [options] inputfile"
parser = OptionParser(usage=usage)
parser.add_option("-s", "--speaker-name-width", type="int", dest="swidth",help="Number of characters for iding speaker", default=5)

options, input_files = parser.parse_args()


speaker_name_width = options.swidth
input = input_files[0]

output = []
for line in open(input):
    parts = line.rstrip().split()
    parts[-1] = parts[-1].replace('_','')
    parts[-1] = parts[-1][0:speaker_name_width+1] + '_' + parts[-1][speaker_name_width+1:]

    output.append(' '.join(parts))

for o in output:
    print o
