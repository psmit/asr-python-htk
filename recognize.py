#!/usr/bin/env python2.6

from htk2.recognizer import HTK_recognizer
from htk2.tools import htk_config
from optparse import OptionParser

usage = "usage: %prog [options] recognition_name modelname file_list dictionary language_model [transform_scp] [transform_mlf] [neighbour_list]"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
parser.add_option('--eval-speaker-chars', dest='eval_speaker_chars', default=3, type='int')
parser.add_option('--transform-speaker-chars', dest='transform_speaker_chars', default=3, type='int')
parser.add_option('-t', '--accent-tree-size', dest='tree_size', default=256, type='int')
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)

name,model,scp,dict,lm = args[:5]

recognizer = HTK_recognizer(htk_config,name,model,scp,dict,lm)

recognizer.recognize(None,'baseline')

recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=options.eval_speaker_chars)
recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=options.eval_speaker_chars,num_nodes=64)

recognizer.recognize(None,'adapted')

if len(args) > 6:

    recognizer.clear_adaptations()

    tscp, tmlf = args[5:7]

    

    recognizer.add_adaptation(tscp,tmlf,num_speaker_chars=options.transform_speaker_chars)
    recognizer.add_adaptation(tscp,tmlf,num_speaker_chars=options.transform_speaker_chars,num_nodes=options.tree_size)


    recognizer.recognize(None,'transform')

    recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars)
    recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars,num_nodes=64)

    recognizer.recognize(None,'transform_stack')

