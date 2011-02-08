#!/usr/bin/env python2.6
from optparse import OptionParser
import os
import sys
from model import HTK_model
from tools import htk_config

usage = "usage: %prog [options] modelname file_list transcription dictionary [model_dir]"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)



if not 4 <= len(args) <= 5:
    parser.print_usage(file=sys.stderr)
    sys.exit(1)

model_dir = None
model_name, scp_list, transcription, dictionary = args[:4]


if len(args) > 4: model_dir = args[5]
if model_dir is None:
    model_dir = os.path.dirname(os.path.abspath(model_name))

model_name = os.path.basename(model_name)

model = HTK_model(model_name, model_dir, htk_config)
model.initialize_new(scp_list,transcription,dictionary,remove_previous=True)

model.expand_word_transcription()

model.flat_start()

for _ in xrange(3):
    model.re_estimate()

    











print "Hello"


