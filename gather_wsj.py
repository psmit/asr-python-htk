#!/usr/bin/env python2.6
from optparse import OptionParser
import sys
import os
import glob
import re


def main():
    usage = "usage: %prog [options] [sets]"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--wsj-directory", dest="wsj_dir", default="/share/puhe/peter/audio/wsj/", help="Base directory with wsj-files")
    parser.add_option("-o", "--output-directory", dest="out_dir", default="", help="Directory for output files")
    parser.add_option("-n", "--name", dest="name", default="", help="Basename of output files")
    parser.add_option("-v", "--vocabulary", dest="vocab", default="", help="If given, the transcriptions are tested for being inside the vocabulary")
    options, sets = parser.parse_args()

    if len(sets) == 0:
        print >> sys.stderr, ", ".join([os.path.basename(os.path.splitext(p)[0]) for p in glob.iglob(options.wsj_dir + '/ndx_links/*.ndx')])
        sys.exit()

    name = options.name
    if len(name) == 0:
        name = ",".join(sets)

    out_dir = options.out_dir
    if len(out_dir) == 0:
        out_dir = './'

    gather(options.wsj_dir, out_dir, name, options.vocab, sets)

def gather(wsj_dir, out_dir, name, vocab, sets):
    scp_files = []

    for s in sets:
        for line in open(os.path.join(wsj_dir, "ndx_links", s+".ndx")):
            if not line.startswith(';'):
                file = wsj_dir + '/' + line.split(':',1)[-1].lstrip().rstrip()
                if not file.endswith('.wv1'):
                    file = file + '.wv1'

                if not os.path.isfile(file):
                    sys.exit("Errorr, not found: '%s'" % file)
                scp_files.append(file)

    needed_dots = set()
    for f in scp_files:
        needed_dots.add(os.path.splitext(os.path.basename(f))[0][:-2] + "00")

    transcriptions = {}

    found_dots = set()
    needed_dot_files = set()
    for d in open(os.path.join(wsj_dir, 'dots')):
        if os.path.splitext(os.path.basename(d.rstrip()))[0] in needed_dots and os.path.splitext(os.path.basename(d.rstrip()))[0] not in found_dots:
            needed_dot_files.add(os.path.join(wsj_dir,d.rstrip()))
            found_dots.add(os.path.splitext(os.path.basename(d.rstrip()))[0])

    if len(needed_dots) != len(needed_dot_files):
        sys.exit("Dot files error")

    for d in needed_dot_files:
        for line in open(d):
            id = line.rstrip().split()[-1][1:-1]
            words = [w.lower() for w in line.rstrip().split()[:-1]]
            real_words = []
            for w in words:
                if not w.startswith('[') and not w.endswith(']') and not w == '.' and not '~' in w:
                    w = w[0] + w[1:].replace('\\', '')
                    w = w.replace('`', '\'')
                    w = w.translate(None, '!:*')
                    if w[0] == '-' or w[0] == '<':
                        w = w[1:]
                    if w[-1] == '-' or w[-1] == '>' or w[-1] == ';':
                        w = w[:-1]
                    w = re.sub('\(.*?\)', '', w)
                    if w == '\\colon':
                        w = '\\:colon'
                    if w == '\\percent':
                        w = '\\%percent'
                    if w == '\\exclamation-point':
                        w = '\\!exclamation-point'
                    real_words.append(w)

            transcriptions[id] = real_words

    if len(vocab) > 0:
        vocab = set([w.rstrip() for w in open(vocab)])

        for k in transcriptions.keys():
            for w in transcriptions[k]:
                if not w in vocab:
                    print "%s not in vocab, %s pruned" % (w,k)
                    del transcriptions[k]
                    break

    with open(os.path.join(out_dir, name+'.mlf'), 'w') as mlf_out:
        print >> mlf_out, "#!MLF!#"
        with open(os.path.join(out_dir, name+'.trn'), 'w') as trn_out:
            with open(os.path.join(out_dir, name+'.scp'), 'w') as scp_out:

                for f in scp_files:
                    name = os.path.splitext(os.path.basename(f))[0]
                    if not name in transcriptions or len(transcriptions) == 0:
                        print >> sys.stderr, "%s misses transcription and is excluded" % name
                    else:
                        print >> scp_out, f
                        print >> trn_out, "%s (%s)" % (" ".join(transcriptions[name]), name)
                        print >> mlf_out, "\"*/%s.lab\"" % name
                        print >> mlf_out, "<s>"
                        for w in transcriptions[name]:
                            print >> mlf_out, w
                        print >> mlf_out, "</s>"
                        print >> mlf_out, "."

if __name__ == "__main__":
    main()
