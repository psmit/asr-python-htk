#!/usr/bin/env python2.6

import re
import sys
import os
import subprocess

from optparse import OptionParser
import glob
import copy
import subprocess
import tempfile

usage = "usage: %prog directories"
parser = OptionParser(usage=usage)
parser.add_option("-c", "--character", action='store_true', dest="character", help="use character scoring",     default=False)
parser.add_option("-v", "--vocabulary", dest="vocab", default="", help="Vocabulary for removing sentences with OOV words")
parser.add_option("-r", "--extra-result-dirs", dest="result_dirs", default="", help="Specify extra dirs with results")
parser.add_option("-s", "--speakers", dest="speakers", default="", help="Specificy comma seperated speakers")
options, directories = parser.parse_args()



result_dirs = ['baseline', 'unsup_si', 'unsup_sat']

speakers = []
if len(options.speakers) > 0:
    speakers = [s for s in options.speakers.split(',') if len(s) > 0]

if len(options.result_dirs) > 0:
    result_dirs.extend(options.result_dirs.split(','))

expermiments = {}

def get_match_part(haystack, match_string, needle):
    regexp = match_string.replace(needle, '(.*)').replace('%h', '.*').replace('%v', '.*')
    m = re.match(regexp, haystack)
    if m is None:
        sys.exit('error in regexps')

    return m.group(1)

def get_oov_sentences(reference, vocab):
    oov_sentences = set()
    for line in open(reference):
        parts = line.split()
        sentence = parts.pop()[1:-1]
        for word in parts:
            if not word in vocab:
                oov_sentences.add(sentence)
                break
    return oov_sentences
                
def make_pruned_trn_file(trn_file, oov_sentences, speakers = []):
    if not os.path.exists(trn_file):
        return trn_file
    file_name = trn_file + '.prunedoov'
    if len(speakers) > 0:
        file_name = file_name + '.' + '.'.join(sorted(speakers))
    with open(file_name,'w') as out_hl:
        for line in open(trn_file):
            parts = line.split()
            sentence = parts.pop()[1:-1]
            if sentence not in oov_sentences:
                if len(speakers) > 0:
                    if(sentence.split('_', 1)[0] not in speakers):
                        continue
                print >> out_hl, line.rstrip()



    out_hl.close()
    return file_name


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
    else:
        for result_dir in result_dirs:
            expermiments[(directory, result_dir)] = (directory, result_dir)
            

    if '%h' in directory and '%v' in directory:
        dim = 3






result_dict = {}

vocab = set()

if options.vocab is not "":
    for line in open(options.vocab):
        vocab.add(line.rstrip().lower())




for experiment in expermiments.keys():
    ref_file = expermiments[experiment][0] + '/reference.trn'

    hyp_file = expermiments[experiment][0] + '/' + expermiments[experiment][1] + '/pass2.trn'

    oov_sentences = set()
    if len(vocab) > 0:
        oov_sentences = get_oov_sentences(ref_file, vocab)
    if len(vocab) > 0 or len(speakers) > 0:
        hyp_file = make_pruned_trn_file(hyp_file, oov_sentences, speakers)

    sclite = ['sclite', '-i', 'rm', '-r', ref_file, 'trn', '-h', hyp_file, 'trn', '-f', '0']
    if options.character:
        sclite.append('-c')

    results = subprocess.Popen(sclite, stdout=subprocess.PIPE).communicate()[0]

    result = 0

    loc = 58
    for line in results.split('\n'):
        if '   Err' in line:
            loc = line.find('   Err')
        if 'Sum/Avg' in line:
            result = float(line[loc:loc+6])

    result_dict[experiment] = result


if dim == 3:
    third_dim = result_dirs
else:
    third_dim = [None]

for td in third_dim:

    if td is not None:
        print ""
        print "-- %s --" % td

    dim_h = []
    dim_v = []

    max_h_len = 0

    v_lens = []

    seen_h = set()
    seen_v = set()
    for exps in sorted(sorted(expermiments.keys(), key=lambda exp: exp[1]), key=lambda exp: exp[0]):
        h = exps[0]
        v = exps[1]
        if not h in seen_h:
            if len(h) > max_h_len:
                max_h_len = len(h)
            dim_h.append(h)
            seen_h.add(h)

        if not v in seen_v:
            v_lens.append(max(4, len(v)))
            dim_v.append(v)
            seen_v.add(v)

    header_format_string = '%' + str(max_h_len) + 's ' + (' '.join(['%' + str(l) + 's' for l in v_lens]))
    line_format_string = '%' + str(max_h_len) + 's ' + (' '.join(['%' + str(l) + '.1f' for l in v_lens]))

    header = ['']
    header.extend(dim_v)
    print header_format_string % tuple(header)

    for h in sorted(dim_h):
        line = [h]
        for v in dim_v:
            if td is not None:
                line.append(result_dict[(h,v, td)])
            else:
                line.append(result_dict[(h,v)])

        print line_format_string % tuple(line)



    
















