#!/usr/bin/env python2.6

from optparse import OptionParser
import sys

from htk2.units import HTK_transcription

usage = "usage: %prog [options] wordsmlf referencetrn"
parser = OptionParser(usage=usage)
parser.add_option('--num-speaker-chars', dest='numspeakerchars', type='int', default=3)


options, args = parser.parse_args()

if len(args) < 2:
    sys.exit("Need at least to arguments")

mlf,trn = args[:2]

tr = HTK_transcription()
tr.read_mlf(mlf,HTK_transcription.WORD)
tr.write_trn(trn,options.numspeakerchars)

