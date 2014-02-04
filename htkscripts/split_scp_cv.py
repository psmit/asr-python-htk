#!/usr/bin/env python2.6

from optparse import OptionParser
import os

usage = "usage: %prog [options] inputfile"
parser = OptionParser(usage=usage)
parser.add_option("-n", "--num-parts", type="int", dest="numparts",help="Number of K in cross validation", default=10)
parser.add_option("-s", "--speaker-name-width", type="int", dest="swidth",help="Number of characters for iding speaker", default=5)

options, input_files = parser.parse_args()


num_parts = options.numparts
speaker_name_width = options.swidth
input = input_files[0]

bins = [ ]
for i in range(0,num_parts):
    bins.append([])

bin_id = -1
cur_name = ""
for line in sorted(open(input)):
    dir,name = os.path.split(line.rstrip())
    if name[0:speaker_name_width] != cur_name:
        bin_id = (bin_id + 1 ) % num_parts
        cur_name = name[0:speaker_name_width]
        print "%s in %d" % (cur_name, bin_id)
    bins[bin_id].append(line.rstrip())

for i in range(0,num_parts):
    with open('train_cv_%d.scp' % i, 'w') as out_file_train:
        for j in range(0,num_parts):
            if j != i:
                for line in bins[j]:
                    print >> out_file_train, line

    with open('eval_cv_%d.scp' % i, 'w') as out_file_eval:
        for line in bins[i]:
            print >> out_file_eval, line





