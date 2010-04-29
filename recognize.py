#!/usr/bin/env python2.6
# Usage: Run this script in the directory where it is working. Standard it searches a file recognition_config. Other configuration file can be given as arguments

import locale
locale.setlocale(locale.LC_ALL, ('en', 'iso-8859-1'))

import data_manipulation
import job_runner
import htk
import htk_logger

import os
import sys
import shutil

from ConfigParser import SafeConfigParser
from optparse import OptionParser

if not os.path.exists('log'): os.mkdir('log')
if not os.path.exists('log/tasks'): os.mkdir('log/tasks')
htk_logger.create_logger('recogniton', 'log/recognition.log')

logger = htk_logger.logger

logger.info("Start recognition")


job_runner.default_options["verbosity"] = 1
job_runner.default_options["memlimit"] = 1000
job_runner.default_options["timelimit"] = "04:00:00"

usage = "usage: %prog [options] configfiles"
parser = OptionParser(usage=usage)
parser.add_option("-n", "--number-nodes", type="int", dest="nodes",help="Number of nodes for jobrunner", default=1)
parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
parser.add_option("-m", "--model-iteration",      type="string", dest="model",      help="model to use", default="hmm61")
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

job_runner.default_options["nodes"] = options.nodes
htk.num_tasks = options.nodes * 48

config = SafeConfigParser({'name': 'EXPERIMENT NAME_TO_BE_FILLED!',
                            'speaker_name_width': '5',
                            'max_pruning': '40000',
                            'beam': '250.0',
                            'end_beam': '-1.0',
                            'lm_scale': '12',
                            'num_tokens': '32'})
config.read(configs if len(configs) > 0 else "recognition_config")



if not config.has_option('model', 'model_dir') or not config.has_option('model', 'config'):
    sys.exit("Please give more configuration")


scp_file = 'eval.scp'
shutil.copyfile(config.get('model', 'model_dir') + '/files/eval.scp', scp_file)

model = config.get('model', 'model_dir') + '/' + options.model
phones_list = config.get('model', 'model_dir') + '/files/tiedlist'
words_mlf = config.get('model', 'model_dir') + '/files/words.mlf'
dict =  config.get('model', 'model_dir') + '/dictionary/dict'
dict_hdecode = config.get('model', 'model_dir') + '/dictionary/dict.hdecode'

lm = config.get('model', 'lm')
lm_rescore = config.get('model', 'lm_rescore')
config_hdecode = config.get('model', 'config')
lat_dir = 'htk_lattices'
lat_dir_rescored = 'rescored_lattices'
speaker_name_width = config.getint('model', 'speaker_name_width')


num_tokens = config.getint('recognition', 'num_tokens')
lm_scale = config.getfloat('recognition', 'lm_scale')
beam = config.getfloat('recognition', 'beam')
end_beam = config.getfloat('recognition', 'end_beam')
if end_beam < 0:
    end_beam = (beam * 2.0) / 3.0
max_pruning = config.getint('recognition', 'max_pruning')


current_step = 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Generating lattices with HDecode'))
    if os.path.exists(lat_dir):
        shutil.rmtree(lat_dir)
    os.mkdir(lat_dir)


    htk.HDecode(current_step, scp_file, model, dict_hdecode, phones_list, lm, lat_dir, num_tokens, [config_hdecode], lm_scale, beam, end_beam, max_pruning)

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Rescoring lattices with lattice-tool'))
    htk.lattice_rescore(current_step, lat_dir, lat_dir_rescored, lm_rescore + '.gz', lm_scale)

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Decoding lattices with lattice-tool'))
    htk.lattice_decode(current_step,lat_dir_rescored, 'rec.mlf', lm_scale)

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Aligning best transcriptions with HVite'))
    htk.HVite(current_step, scp_file, model, dict, phones_list, 'rec.mlf', 'rec_aligned_phone.mlf')

if not os.path.exists('xforms_files'): os.mkdir('xforms_files')
if not os.path.exists('classes'): os.mkdir('classes')

tree_cmllr_config = 'xforms_files/config.tree_cmllr'
base_cmllr_config = 'xforms_files/config.base_cmllr'
regtree_hed =  'xforms_files/regtree.hed'
classes = 'classes'
regtree_tree = 'xforms/regtree.tree'
global_f = classes + '/global'

current_step += 1
if current_step >= options.step:
    with open(regtree_hed, 'w') as hed_file:
        print >> hed_file, 'RN "global"'
        print >> hed_file, 'LS "%s/stats"' % model
        print >> hed_file, 'RC 32 "regtree"'

    if os.path.exists('xforms'): shutil.rmtree('xforms')
    os.mkdir('xforms')

    logger.info("Start step: %d (%s)" % (current_step, 'Generate regression tree'))
    htk.HHEd(current_step, model, 'xforms', regtree_hed, phones_list, '/dev/null')

    with open(base_cmllr_config, 'w') as cmllr_config_stream:
        print >> cmllr_config_stream, "HADAPT:TRACE                  = 61\n\
         HADAPT:TRANSKIND              = CMLLR\n\
         HADAPT:USEBIAS                = TRUE\n\
         HADAPT:BASECLASS         = %s\n\
         HADAPT:KEEPXFORMDISTINCT = TRUE\n\
         HADAPT:ADAPTKIND              = BASE\n\
         HMODEL:SAVEBINARY             = FALSE\n" % (global_f)

    with open(tree_cmllr_config, 'w') as cmllr_config_stream:
        print >> cmllr_config_stream, "HADAPT:TRACE                  = 61\n\
         HADAPT:TRANSKIND              = CMLLR\n\
         HADAPT:USEBIAS                = TRUE\n\
         HADAPT:REGTREE                = %s\n\
         HADAPT:KEEPXFORMDISTINCT = TRUE\n\
         HADAPT:ADAPTKIND              = TREE\n\
         HMODEL:SAVEBINARY             = FALSE\n" % (regtree_tree)
current_step += 1
if current_step >= options.step:

    with open(global_f, 'w') as global_file:
        print >> global_file, "~b \"global\" \n\
        <MMFIDMASK> *\n\
        <PARAMETERS> MIXBASE\n\
        <NUMCLASSES> 1\n\
        <CLASS> 1 {*.state[2-4].mix[1-100]} "
    logger.info("Start step: %d (%s)" % (current_step, 'Estimate global transforms'))
    htk.HERest_estimate_transform(current_step, scp_file, model, 'xforms', phones_list, 'rec_aligned_phone.mlf', ['config/config', base_cmllr_config], speaker_name_width, 'mllr1')


current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Estimate tree transforms'))
    htk.HERest_estimate_transform(current_step, scp_file, model, 'xforms', phones_list, 'rec_aligned_phone.mlf', ['config/config', tree_cmllr_config], speaker_name_width, 'mllr2', [('xforms', 'mllr1')])

ada_lat_dir = 'htk_lattices_ada'
ada_lat_dir_rescored = 'rescored_lattices_ada'


if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Generating lattices with HDecode'))
    if os.path.exists(ada_lat_dir):
        shutil.rmtree(ada_lat_dir)
    os.mkdir(ada_lat_dir)

    htk.HDecode(current_step, scp_file, model, dict_hdecode, phones_list, lm, ada_lat_dir, num_tokens, [config_hdecode, tree_cmllr_config], lm_scale, beam, end_beam, max_pruning, [('xforms', 'mllr2')])

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Rescoring lattices with lattice-tool'))
    htk.lattice_rescore(current_step, ada_lat_dir, ada_lat_dir_rescored, lm_rescore + '.gz', lm_scale)

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Decoding lattices with lattice-tool'))
    htk.lattice_decode(current_step,ada_lat_dir_rescored, 'rec.mlf', lm_scale)
    sys.exit()

current_step +=1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Deleting lattices'))
    if os.path.exists(lat_dir):
        shutil.rmtree(lat_dir)
    if os.path.exists(lat_dir_rescored):
        shutil.rmtree(lat_dir_rescored)
    if os.path.exists(ada_lat_dir):
        shutil.rmtree(ada_lat_dir)
    if os.path.exists(ada_lat_dir_rescored):
        shutil.rmtree(ada_lat_dir_rescored)

current_step +=1
if current_step >= options.step:
    data_manipulation.mlf_to_trn(words_mlf, 'reference.trn', speaker_name_width)
    data_manipulation.mlf_to_trn('rec.mlf', 'rescore_decode.trn', speaker_name_width)
    data_manipulation.mlf_to_trn('out.mlf', 'decode.trn', speaker_name_width)


