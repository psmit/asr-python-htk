#!/usr/bin/env python2.6

from htk2.recognizer import HTK_recognizer
from htk2.tools import htk_config
from optparse import OptionParser

usage = "usage: %prog [options] recognition_name modelname file_list dictionary language_model [transform_scp] [transform_mlf] [neighbour_list]"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
parser.add_option('--eval-speaker-chars', dest='eval_speaker_chars', default=3, type='int')
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)

name,model,scp,dict,lm = args[:5]

recognizer = HTK_recognizer(htk_config,name,model,scp,dict,lm)

recognizer.recognize(None,'baseline')


if len(args) > 6:

    for s in [32,64,128,256,384,512,640,768,896,1024]:


        tscp, tmlf = args[5:7]

        recognizer.add_adaptation(tscp,tmlf,num_speaker_chars=options.eval_speaker_chars)
        recognizer.add_adaptation(tscp,tmlf,num_speaker_chars=options.eval_speaker_chars,num_nodes=s)


        recognizer.recognize(None,'transform.size-%d'%s)

        recognizer.clear_adaptations()

#    recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars)
#    recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars,num_nodes=64)
#
#    recognizer.recognize(None,'transform_stack')

