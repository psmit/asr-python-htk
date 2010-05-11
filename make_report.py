#!/usr/bin/env python2.6

import re
import sys
from subprocess import Popen, PIPE

from optparse import OptionParser
from glob import glob
import copy

usage = "usage: %prog directories"
parser = OptionParser(usage=usage)
parser.add_option("-c", "--character", action='store_true', dest="character", help="use character scoring",     default=False)
options, directories = parser.parse_args()

result_dirs = ['baseline', 'unsup_si', 'unsup_sat']

expermiments = {}

def get_match_part(haystack, match_string, needle):
    regexp = match_string.replace(needle, '(.*)').replace('%h', '.*').replace('%v', '.*')
    m = re.match(regexp, haystack)
    if m is None:
        sys.exit('error in regexps')

    return m.group(1)

dim = 2

if len(directories) > 1:
    for directory in directories:
        for result_dir in result_dirs:
            expermiments[(directory, result_dir)] = (directory, result_dir)

elif len(directories) == 1:
    directory = directories[0]
    if '%h' in directory or '%v' in directory:
        matched_directories = glob.glob(directory.replace('%h', '*').replace('%v', '*'))

        for md in matched_directories:
            l = []
            if '%h' in directory:
                l.append(get_match_part(md, directory, '%h'))
            if '%v' in directory:
                l.append(get_match_part(md, directory, '%v'))

            for result_dir in result_dirs:
                l2 = copy.copy(l)
                l2.append(result_dir)
                expermiments[tuple(l2)] = (md, result_dir)

    if '%h' in directory and '%v' in directory:
        dim = 3


result_dict = {}

for experiment in expermiments.keys():
    ref_file = expermiments[experiment][0] + '/reference.trn'
    hyp_file = expermiments[experiment][0] + '/' + expermiments[experiment][1] + '/pass2.trn'

    sclite = ['sclite', '-i', 'rm', '-r', ref_file, 'trn', '-h', hyp_file, 'trn', '-f', '0']
    if options.character:
        sclite.append('-c')

    results = Popen(sclite, stderr=None, stdin=None, stdout=PIPE).communicate()[0]

    result = 0

    for line in results.split('\n'):
        if 'Sum/Avg' in line:
            result = float(line[57:64])

    result_dict[experiment] = result


if dim == 3:
    third_dim = result_dirs
else:
    third_dim = [None]

for td in third_dim:

    if td is not None:
        print ""
        print "-- %s --" % td

    if dim == 2:
        dim_h = set()
        dim_v = set()

        max_h_len = 0

        v_lens = []

        for exps in expermiments.keys():
            h = exps[0]
            v = exps[1]
            if len(h) > max_h_len:
                max_h_len = h

            v_lens.append(max(4, len(v)))

            dim_h.add(h)
            dim_v.add(v)

        header_format_string = '%' + max_h_len + 's ' + (' '.join(['%' + l + 's' for l in v_lens]))
        line_format_string = '%' + max_h_len + 's ' + (' '.join(['%' + l + 'f' for l in v_lens]))

        header = [''].extend(dim_v)
        print header_format_string % tuple(header)

        for h in sorted(dim_h):
            line = [h]
            for v in dim_v:
                if td is not None:
                    line.append(result_dict[(h,v, td)])
                else:
                    line.append(result_dict[(h,v)])

            print line_format_string % tuple(line)



    
















