#!/usr/bin/env python2.6
# Usage: Run this script in the directory where it is working. Standard it searches a file train_config. Other configuration file can be given as arguments

import locale
locale.setlocale(locale.LC_ALL, ('en', 'iso-8859-1'))


import data_manipulation
import job_runner
import htk
import htk_logger

import logging
import os
import os.path
import shutil
import sys

from ConfigParser import SafeConfigParser
from optparse import OptionParser

if not os.path.exists('log'): os.mkdir('log')
htk_logger.create_logger('htk_train', 'log/htk_train.log')

logger = htk_logger.logger

logger.info("Start htk_train")


job_runner.default_options["verbosity"] = 1
job_runner.default_options["memlimit"] = 1000
job_runner.default_options["timelimit"] = "00:15:00"

usage = "usage: %prog [options] configfiles"
parser = OptionParser(usage=usage)
parser.add_option("-n", "--number-nodes", type="int", dest="nodes",help="Number of nodes for jobrunner", default=1)
parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

job_runner.default_options["nodes"] = options.nodes
htk.num_tasks = options.nodes * 48

config = SafeConfigParser({'name': 'EXPERIMENT NAME_TO_BE_FILLED!',
                            'prefix': '',
                            'minvariance': 0.05,
                            'HERest_pruning': '300.0 500.0 2000.0',
                            'tying_threshold': 1000.0,
                            'required_occupation': 200.0,
                            'speaker_name_width': 5,
                            'word_suffix': ''})
config.read(configs if len(configs) > 0 else "train_config")


current_step = 0
experiment_name = config.get('DEFAULT', 'name')
data_manipulation.createLogDirs()
target_hmm_dir = ""

logger.info("Starting step: %d" % options.step)

dict = 'dictionary/dict'
# Data Collection step
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Data collection'))
    dicts = []

    corpora = []
    
    cur_dict_id = 1
    while config.has_option("dict"+str(cur_dict_id), "location"):
        dicts.append([config.get("dict"+str(cur_dict_id), "location"),
                        config.get("dict"+str(cur_dict_id), "prefix"),
                        config.get("dict"+str(cur_dict_id), "word_suffix")])
        cur_dict_id += 1
    
    if len(dicts) == 0: sys.exit("No Dictionaries Found!")
    
    cur_corpus_id = 1
    while config.has_option("corpus"+str(cur_corpus_id), "location"):
        corpora.append([config.get("corpus"+str(cur_corpus_id), "location"),
                        config.get("corpus"+str(cur_corpus_id), "prefix"),
                        config.get("corpus"+str(cur_corpus_id), "word_suffix")])
        cur_corpus_id += 1
    
    if len(corpora) == 0: sys.exit("No Corpora Found!")
    
    data_manipulation.import_dictionaries(dicts)
    data_manipulation.import_corpora(corpora)
    
    mkmono0_led = 'config/mkmono0.led'
    mkmono1_led = 'config/mkmono1.led'
    # Make phone transcriptions
    if not os.path.exists(mkmono0_led): sys.exit("Not Found: " + mkmono0_led)
    if not os.path.exists(mkmono1_led): sys.exit("Not Found: " + mkmono1_led)
    if os.path.isdir('files'): shutil.rmtree('files')
    os.mkdir('files')

    excluded = data_manipulation.prune_transcriptions(dict, 'corpora/words.mlf', 'files/words.mlf')
    data_manipulation.update_exclude_list('files/exclude_list', excluded, ['corpora/train.scp','corpora/eval.scp','corpora/devel.scp'], ['files/train.scp','files/eval.scp','files/devel.scp'])

    htk.HLEd(current_step, 'files/words.mlf', mkmono0_led, '*', 'files/monophones0', 'files/mono0.mlf', dict)
    htk.HLEd(current_step, 'files/words.mlf', mkmono1_led, '*', 'files/monophones1', 'files/mono1.mlf', dict)
    
    
current_step += 1   

# Set some common variables
scpfile = 'files/train.scp'
configfile = 'config/config'
if not os.path.exists(scpfile): sys.exit("Not Found: " + scpfile)
if not os.path.exists(configfile): sys.exit("Not Found: " + configfile)

htk.default_config_file = configfile
htk.default_HERest_pruning = config.get("DEFAULT", "HERest_pruning").split(None, 2)

phones_list = 'files/monophones0'
transcriptions = 'files/mono0.mlf'



# Flat start step, calculate global variances with HCompV
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Initialize model with global variance'))
    
    source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
    
    protofile = 'config/proto'
    if not os.path.exists(protofile): sys.exit("Not Found: " + protofile)
    htk.HCompV(current_step, scpfile, target_hmm_dir, protofile, config.get('DEFAULT', 'minvariance'))
    
    data_manipulation.make_model_from_proto(target_hmm_dir, 'files/monophones0')


# Re estimate model 3 times
for i in range(0,3):
    current_step += 1

    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
        
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, binary=(i != 3))
    

current_step += 1

# Introduce sp model by copying it from sil
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Introduce sp model'))
    
    source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
    
    data_manipulation.add_sp_to_phonelist(phones_list, 'files/monophones1')
    data_manipulation.copy_sil_to_sp(source_hmm_dir, target_hmm_dir)
    

phones_list = 'files/monophones1'
transcriptions = 'files/mono1.mlf'

current_step += 1

# Tie the middle sil state to the sp state
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Tie silence state to sp'))
    
    source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
    
    sil_hed = "config/sil.hed"
    if not os.path.exists(sil_hed): sys.exit("Not Found: " + sil_hed)
    
    htk.HHEd(current_step, source_hmm_dir, target_hmm_dir, sil_hed, phones_list)

    
# Re estimate model 3 times
for i in range(0,3):
    current_step += 1

    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
    
transcriptions = 'files/mono1_aligned.mlf'

# same step still, realign data
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Realign data'))
    
    htk.HVite(current_step, scpfile, target_hmm_dir, dict, phones_list, 'files/words.mlf', transcriptions)

    os.rename(scpfile, scpfile +'.backup')
    data_manipulation.filter_scp_by_mlf(scpfile +'.backup', scpfile, transcriptions, 'files/excluded_utterances')
    
scpfile = 'files/train.scp'

# Re estimate model 4 times
for i in range(0,4):
    current_step += 1
    
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
    

current_step += 1

# Make triphone transcriptions and transform model to triphone
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Transform model to triphones'))
    
    source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
    
    led_file = 'config/mktri.led'
    if not os.path.exists(led_file): sys.exit("Not Found: " + led_file)
    
    triphones_list = 'files/triphones'
    htk.HLEd(current_step, transcriptions, led_file, '*', triphones_list, 'files/tri.mlf')
    data_manipulation.remove_triphone_sil(triphones_list, True)
    data_manipulation.remove_triphone_sil('files/tri.mlf')
    
    data_manipulation.make_tri_hed(triphones_list, phones_list, 'files/mktri.hed')
    
    htk.HHEd(current_step, source_hmm_dir, target_hmm_dir, 'files/mktri.hed', phones_list)
    
phones_list = 'files/triphones'
transcriptions = 'files/tri.mlf'
    

# Re estimate model 3 times
for i in range(0,3):
    current_step += 1
    
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, True if i == 2 else False)
    

current_step += 1

# Tie the triphones together
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Tying the model'))
    source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
    
    data_manipulation.make_fulllist('files/monophones1', 'files/fulllist')
    
    rules = []
    rules_id = 1
    while config.has_option("tierules"+str(rules_id), "location"):
        rules.append([config.get("tierules"+str(rules_id), "location"),
                        config.get("tierules"+str(rules_id), "prefix")])
        rules_id += 1
        
    data_manipulation.make_tree_hed(rules, 'files/monophones1', 'files/tree.hed', config.getfloat("triphonetying", "tying_threshold"), config.getfloat("triphonetying", "required_occupation"), source_hmm_dir + '/stats', 'files/fulllist', 'files/tiedlist', 'files/trees')
    
    htk.HHEd(current_step, source_hmm_dir, target_hmm_dir, 'files/tree.hed', phones_list)
    
    
phones_list = 'files/tiedlist'
    
# Re estimate model 3 times
for i in range(0,3):
    current_step += 1

    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
    
#Mixture splitting !
for mix in [1, 2, 4, 6, 8, 12, 16]:
    current_step += 1
    if current_step >= options.step:
        logger.info("Start step: %d (%s)" % (current_step, 'Mixture splitting'))
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
        hed_file =  'files/mix%d.hed' % mix
        with open(hed_file, 'w') as hed:
            print >> hed, "MU %d {*.state[2-4].stream[1].mix}" % mix
            print >> hed, "MU %d {sil.state[2-4].stream[1].mix}" % 2*mix

        htk.HHEd(current_step,source_hmm_dir, target_hmm_dir,hed_file,phones_list)


    # Re estimate model 4 times
    for i in range(0,4):
        current_step += 1

        if current_step >= options.step:
            logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest'))
            source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)

            htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, mix == 16 and i == 3)

####################################
#Speaker Adaptive Training
####################################
for number_sat_round in range(0,4):

    current_step += 1

    cmllr_config = 'files/config.cmllr.%d' % number_sat_round

    if current_step >= options.step:
        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)

        regtree_hed =  'files/regtree_%s.hed' % number_sat_round
        with open(regtree_hed, 'w') as hed_file:
            print >> hed_file, 'LS "%s/stats"' % source_hmm_dir
            print >> hed_file, 'RC 32 "regtree"'

        if os.path.exists(source_hmm_dir + '/cmllr'): shutil.rmtree(source_hmm_dir + '/cmllr')
        os.mkdir(source_hmm_dir + '/cmllr')
        logger.info("Start step: %d (%s)" % (current_step, 'Generate regression tree'))
        htk.HHEd(current_step, source_hmm_dir, source_hmm_dir + '/cmllr', regtree_hed, phones_list, '/dev/null')



        with open(cmllr_config, 'w') as cmllr_config_stream:
            print >> cmllr_config_stream, "HADAPT:TRACE                  = 61\n\
             HADAPT:TRANSKIND              = CMLLR\n\
             HADAPT:USEBIAS                = TRUE\n\
             HADAPT:REGTREE                = %s\n\
             HADAPT:ADAPTKIND              = TREE\n\
             HMODEL:SAVEBINARY             = FALSE\n" % (source_hmm_dir +'/cmllr/regtree.tree')
            #             HADAPT:BLOCKSIZE              = \"IntVec 3 13 13 13\"\n\

        logger.info("Start step: %d (%s)" % (current_step, 'Estimate transform'))
        htk.HERest_estimate_transform(current_step, scpfile, source_hmm_dir, source_hmm_dir + '/cmllr', phones_list, transcriptions, ['config/config', cmllr_config], int(config.get('corpora', 'speaker_name_width')))

        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest (SAT)'))
        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, True, ['config/config', cmllr_config], source_hmm_dir + '/cmllr',  int(config.get('corpora', 'speaker_name_width')))


#    current_step += 1
#
#    if current_step >= options.step:
#        logger.info("Start step: %d (%s)" % (current_step, 'Re-estimate model with HERest (SAT)'))
#        source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
#
#        htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, True, ['config/config', cmllr_config], source_hmm_dir + '/cmllr',  int(config.get('corpora', 'speaker_name_width')))



print "Finished!"


