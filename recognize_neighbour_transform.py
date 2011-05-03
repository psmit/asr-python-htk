#!/usr/bin/env python2.6

from htk2.recognizer import HTK_recognizer
from htk2.tools import htk_config
from optparse import OptionParser
from remote_run import System

from os import symlink, mkdir
from os.path import join, basename,splitext
from htk2.units import HTK_transcription

from random import shuffle

usage = "usage: %prog [options] recognition_name modelname file_list dictionary language_model transform_scp transform_mlf neighbour_list"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
parser.add_option('--eval-speaker-chars', dest='eval_speaker_chars', default=3, type='int')
parser.add_option('--transform-speaker-chars', dest='transform_speaker_chars', default=3, type='int')
parser.add_option('-t', '--accent-tree-size', dest='tree_size', default=256, type='int')
parser.add_option('-n', '--num-neighbours',dest='num_neighbours,',default=5,type='int')
parser.add_option('-a', '--num-adaptation-files', dest='num_adaptation_files', default=0,type='int')
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)

name,model,scp,dict,lm,scp,mlf,neighbourlist = args[:8]

recognizer = HTK_recognizer(htk_config,name,model,scp,dict,lm)

recognizer.recognize(None,'baseline')

#recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=options.eval_speaker_chars)
#recognizer.add_adaptation(scp,recognizer.name+'.baseline.mlf',num_speaker_chars=options.eval_speaker_chars,num_nodes=64)
#
#recognizer.recognize(None,'adapted')
#recognizer.clear_adaptations()


tmp_dir = System.get_global_temp_dir()

transform_scp = join(tmp_dir, 'neighbour_transform.scp')
transform_mlf = join(tmp_dir, 'neighbour_transform.mlf')
file_dir = join(tmp_dir, 'files')
mkdir(file_dir)

neighbour_dict = {}
for line in open(neighbourlist):
    parts = line.strip().split()
    sp = parts[0]
    neighbors = [n for n in parts[2:] if n is not sp]

    neighbour_dict[sp] = neighbors[:options.num_neighbours]

transform_files = {}
for line in open(transform_scp):
    sp = basename(line.strip())[:3]
    if sp not in transform_files:
        transform_files[sp] = []
    transform_files[sp].append(line.strip())

mlf = HTK_transcription()
mlf.read_mlf(transform_mlf,target=HTK_transcription.WORD)


#trans_mlf = HTK_transcription()

with open(transform_scp, 'w') as transform_desc:
    for sp in neighbour_dict.keys():
        neighbors = neighbour_dict[sp]
        t_files = []
        for n in neighbors:
            t_files.extend(transform_files[n])
        t_files = shuffle(t_files)

        if options.num_adaptation_files > 0:
            t_files = t_files[:options.num_adaptation_files]

        for t in t_files:
            f = splitext(basename(t))[0]
            mlf.transcriptions[HTK_transcription.WORD]["%s_%s"%(sp,f)] = mlf.transcriptions[HTK_transcription.WORD][f]

            new_f = join(file_dir,"%s_%s"%(sp,basename(t)))
            symlink(t,new_f)
            print >> transform_desc, new_f

mlf.write_mlf(transform_mlf)

    

recognizer.add_adaptation(transform_scp,transform_mlf,num_speaker_chars=options.transform_speaker_chars)
recognizer.add_adaptation(transform_scp,transform_mlf,num_speaker_chars=options.transform_speaker_chars,num_nodes=options.tree_size)


recognizer.recognize(None,'neighbour_transform')

#recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars)
#recognizer.add_adaptation(scp,recognizer.name+'.transform.mlf',num_speaker_chars=options.eval_speaker_chars,num_nodes=64)
#
#recognizer.recognize(None,'neighbour_transform_stack')

