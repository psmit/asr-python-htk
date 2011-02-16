#!/usr/bin/env python2.6

from htk2.recognizer import HTK_recognizer
from htk2.tools import htk_config
from optparse import OptionParser

usage = "usage: %prog [options] recognition_name modelname file_list dictionary language_model"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)

name,model,scp,dict,lm = args[:5]

recognizer = HTK_recognizer(htk_config,name,model,scp,dict,lm)

recognizer.recognize(None,'baseline')

recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=3)
recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=3,num_nodes=32)

recognizer.recognize(None,'adapted')


