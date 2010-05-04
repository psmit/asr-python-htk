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
parser.add_option("-n", "--num-tasks", type="int", dest="numtasks",help="Number of different tasks", default=50)
parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

htk.num_tasks = options.numtasks

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

#model configuration
si_model = config.get('model', 'model_dir') + '/' + config.get('model', 'si_model')
sat_model = config.get('model', 'model_dir') + '/' + config.get('model', 'sat_model')

phones_list = config.get('model', 'model_dir') + '/files/tiedlist'
words_mlf = config.get('model', 'model_dir') + '/files/words.mlf'

dict =  config.get('model', 'model_dir') + '/dictionary/dict'
dict_hdecode = config.get('model', 'model_dir') + '/dictionary/dict.hdecode'
config_hdecode = config.get('model', 'config')
orig_config = config.get('model', 'model_dir') + '/config/config'

lm = config.get('model', 'lm')
lm_rescore = config.get('model', 'lm_rescore')

speaker_name_width = config.getint('model', 'speaker_name_width')

# Recognition configuration
num_tokens = config.getint('recognition', 'num_tokens')
lm_scale = config.getfloat('recognition', 'lm_scale')
beam = config.getfloat('recognition', 'beam')
end_beam = config.getfloat('recognition', 'end_beam')
if end_beam < 0:
    end_beam = (beam * 2.0) / 3.0
max_pruning = config.getint('recognition', 'max_pruning')


# Experiment configuration
experiments = set([exp.lstrip().rstrip() for exp in config.get('experiments','experiments').split(',')])

htk.default_config_file = orig_config
htk.default_HERest_pruning = ['300.0', '500.0', '2000.0']


current_step = 0

logger.info("Start step: %d (%s)" % (current_step, 'Making reference trn'))
data_manipulation.mlf_to_trn(words_mlf, 'reference.trn', speaker_name_width)

baseline_dir = 'baseline'
baseline_lat_dir = baseline_dir + '/lattices.htk'
baseline_lat_dir_rescored = baseline_dir + '/lattices.rescored'
baseline_pass1_mlf = baseline_dir + '/pass1.mlf'
baseline_pass2_mlf = baseline_dir + '/pass2.mlf'

if 'baseline' in experiments:

    pass1_trn = baseline_dir + '/pass1.trn'
    pass2_trn = baseline_dir + '/pass2.trn'


    if not os.path.exists(baseline_dir):
        os.mkdir(baseline_dir)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Generating lattices with HDecode'))
        if os.path.exists(baseline_lat_dir): shutil.rmtree(baseline_lat_dir)
        os.mkdir(baseline_lat_dir)

        htk.HDecode(current_step, scp_file, si_model, dict_hdecode, phones_list, lm, baseline_lat_dir, num_tokens, baseline_pass1_mlf, [config_hdecode], lm_scale, beam, end_beam, max_pruning)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Rescoring lattices with lattice-tool'))
        if os.path.exists(baseline_lat_dir_rescored): shutil.rmtree(baseline_lat_dir_rescored)
        htk.lattice_rescore(current_step, baseline_lat_dir, baseline_lat_dir_rescored, lm_rescore + '.gz', lm_scale)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Decoding lattices with lattice-tool'))
        htk.lattice_decode(current_step,baseline_lat_dir_rescored, baseline_pass2_mlf, lm_scale)


    data_manipulation.mlf_to_trn(baseline_pass1_mlf, pass1_trn, speaker_name_width)
    data_manipulation.mlf_to_trn(baseline_pass2_mlf, pass2_trn, speaker_name_width)

unsupsi_dir = 'unsup_si'
unsupsi_lat_dir = unsupsi_dir + '/lattices.htk'
unsupsi_lat_dir_rescored = unsupsi_dir + '/lattices.rescored'

if 'unsupsi' in experiments:

    adapt_mlf = unsupsi_dir + '/adapt.mlf'
    pass1_mlf = unsupsi_dir + '/pass1.mlf'
    pass2_mlf = unsupsi_dir + '/pass2.mlf'
    pass1_trn = unsupsi_dir + '/pass1.trn'
    pass2_trn = unsupsi_dir + '/pass2.trn'

    xforms_dir = unsupsi_dir + '/xforms'
    classes_dir = unsupsi_dir + '/classes'
    files_dir = unsupsi_dir + '/files'

    if not os.path.exists(unsupsi_dir): os.mkdir(unsupsi_dir)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Aligning best transcriptions with HVite'))
        htk.HVite(current_step, scp_file, si_model, dict, phones_list, baseline_pass2_mlf, adapt_mlf, 'rec')

    if not os.path.exists(xforms_dir): os.mkdir(xforms_dir)
    if not os.path.exists(classes_dir): os.mkdir(classes_dir)
    if not os.path.exists(files_dir): os.mkdir(files_dir)

    tree_cmllr_config = files_dir+'/config.tree_cmllr'
    base_cmllr_config = files_dir+'/config.base_cmllr'
    regtree_hed =  files_dir+'/regtree.hed'
    regtree_tree = xforms_dir+'/regtree.tree'
    global_f = classes_dir + '/global'

    current_step += 1
    if current_step >= options.step:
        with open(regtree_hed, 'w') as hed_file:
            print >> hed_file, 'RN "global"'
            print >> hed_file, 'LS "%s/stats"' % si_model
            print >> hed_file, 'RC 32 "regtree"'

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

        with open(global_f, 'w') as global_file:
            print >> global_file, "~b \"global\" \n\
            <MMFIDMASK> *\n\
            <PARAMETERS> MIXBASE\n\
            <NUMCLASSES> 1\n\
            <CLASS> 1 {*.state[2-4].mix[1-100]} "


        logger.info("Start step: %d (%s)" % (current_step, 'Generate regression tree'))
        htk.HHEd(current_step, si_model, xforms_dir, regtree_hed, phones_list, '/dev/null')


    current_step += 1
    if current_step >= options.step:


        logger.info("Start step: %d (%s)" % (current_step, 'Estimate global transforms'))
        htk.HERest_estimate_transform(current_step, scp_file, si_model, xforms_dir, phones_list, adapt_mlf, [orig_config, base_cmllr_config], speaker_name_width, 'mllr1')


    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Estimate tree transforms'))
        htk.HERest_estimate_transform(current_step, scp_file, si_model, xforms_dir, phones_list, adapt_mlf, [orig_config, tree_cmllr_config], speaker_name_width, 'mllr2', [(xforms_dir, 'mllr1')])


    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Generating lattices with HDecode'))
        if os.path.exists(unsupsi_lat_dir): shutil.rmtree(unsupsi_lat_dir)
        os.mkdir(unsupsi_lat_dir)

        htk.HDecode(current_step, scp_file, si_model, dict_hdecode, phones_list, lm, unsupsi_lat_dir, num_tokens, pass1_mlf, [config_hdecode, tree_cmllr_config], lm_scale, beam, end_beam, max_pruning, [(xforms_dir, 'mllr2')])

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Rescoring lattices with lattice-tool'))
        if os.path.exists(unsupsi_lat_dir_rescored): shutil.rmtree(unsupsi_lat_dir_rescored)
        htk.lattice_rescore(current_step, unsupsi_lat_dir, unsupsi_lat_dir_rescored, lm_rescore + '.gz', lm_scale)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Decoding lattices with lattice-tool'))
        htk.lattice_decode(current_step,unsupsi_lat_dir_rescored, pass2_mlf, lm_scale)
        

    data_manipulation.mlf_to_trn(pass1_mlf, pass1_trn, speaker_name_width)
    data_manipulation.mlf_to_trn(pass2_mlf, pass2_trn, speaker_name_width)


unsupsat_dir = 'unsup_sat'
unsupsat_lat_dir = unsupsat_dir + '/lattices.htk'
unsupsat_lat_dir_rescored = unsupsat_dir + '/lattices.rescored'

if 'unsupsat' in experiments:

    adapt_mlf = unsupsat_dir + '/adapt.mlf'
    pass1_mlf = unsupsat_dir + '/pass1.mlf'
    pass2_mlf = unsupsat_dir + '/pass2.mlf'
    pass1_trn = unsupsat_dir + '/pass1.trn'
    pass2_trn = unsupsat_dir + '/pass2.trn'

    xforms_dir = unsupsat_dir + '/xforms'
    classes_dir = unsupsat_dir + '/classes'
    files_dir = unsupsat_dir + '/files'

    if not os.path.exists(unsupsat_dir): os.mkdir(unsupsat_dir)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Aligning best transcriptions with HVite'))
        htk.HVite(current_step, scp_file, si_model, dict, phones_list, baseline_pass2_mlf, adapt_mlf, 'rec')

    if not os.path.exists(xforms_dir): os.mkdir(xforms_dir)
    if not os.path.exists(classes_dir): os.mkdir(classes_dir)
    if not os.path.exists(files_dir): os.mkdir(files_dir)

    tree_cmllr_config = files_dir+'/config.tree_cmllr'
    base_cmllr_config = files_dir+'/config.base_cmllr'
    regtree_hed =  files_dir+'/regtree.hed'
    regtree_tree = xforms_dir+'/regtree.tree'
    global_f = classes_dir + '/global'

    current_step += 1
    if current_step >= options.step:
        with open(regtree_hed, 'w') as hed_file:
            print >> hed_file, 'RN "global"'
            print >> hed_file, 'LS "%s/stats"' % si_model
            print >> hed_file, 'RC 32 "regtree"'

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

        with open(global_f, 'w') as global_file:
            print >> global_file, "~b \"global\" \n\
            <MMFIDMASK> *\n\
            <PARAMETERS> MIXBASE\n\
            <NUMCLASSES> 1\n\
            <CLASS> 1 {*.state[2-4].mix[1-100]} "


        logger.info("Start step: %d (%s)" % (current_step, 'Generate regression tree'))
        htk.HHEd(current_step, si_model, xforms_dir, regtree_hed, phones_list, '/dev/null')


    current_step += 1
    if current_step >= options.step:


        logger.info("Start step: %d (%s)" % (current_step, 'Estimate global transforms'))
        htk.HERest_estimate_transform(current_step, scp_file, sat_model, xforms_dir, phones_list, adapt_mlf, [orig_config, base_cmllr_config], speaker_name_width, 'mllr1')


    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Estimate tree transforms'))
        htk.HERest_estimate_transform(current_step, scp_file, sat_model, xforms_dir, phones_list, adapt_mlf, [orig_config, tree_cmllr_config], speaker_name_width, 'mllr2', [(xforms_dir, 'mllr1')])


    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Generating lattices with HDecode'))
        if os.path.exists(unsupsat_lat_dir): shutil.rmtree(unsupsat_lat_dir)
        os.mkdir(unsupsat_lat_dir)

        htk.HDecode(current_step, scp_file, sat_model, dict_hdecode, phones_list, lm, unsupsat_lat_dir, num_tokens, pass1_mlf, [config_hdecode, tree_cmllr_config], lm_scale, beam, end_beam, max_pruning, [(xforms_dir, 'mllr2')])

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Rescoring lattices with lattice-tool'))
        if os.path.exists(unsupsat_lat_dir_rescored): shutil.rmtree(unsupsat_lat_dir_rescored)
        htk.lattice_rescore(current_step, unsupsat_lat_dir, unsupsat_lat_dir_rescored, lm_rescore + '.gz', lm_scale)

    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Decoding lattices with lattice-tool'))
        htk.lattice_decode(current_step,unsupsat_lat_dir_rescored, pass2_mlf, lm_scale)

    data_manipulation.mlf_to_trn(pass1_mlf, pass1_trn, speaker_name_width)
    data_manipulation.mlf_to_trn(pass2_mlf, pass2_trn, speaker_name_width)
    

#current_step +=1
#if current_step >= options.step:
#    logger.info("Start step: %d (%s)" % (current_step, 'Deleting lattices'))
#    if os.path.exists(lat_dir):
#        shutil.rmtree(lat_dir)
#    if os.path.exists(lat_dir_rescored):
#        shutil.rmtree(lat_dir_rescored)
#    if os.path.exists(ada_lat_dir):
#        shutil.rmtree(ada_lat_dir)
#    if os.path.exists(ada_lat_dir_rescored):
#        shutil.rmtree(ada_lat_dir_rescored)
#

