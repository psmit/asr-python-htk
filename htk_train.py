#!/usr/bin/python
# Usage: Run this script in the directory where it is working. Standard it searches a file train_config. Other configuration file can be given as arguments

import job_runner
import htk
import data_manipulation

import os
import shutil
import sys

from ConfigParser import SafeConfigParser
from optparse import OptionParser


	
job_runner.default_options["verbosity"] = 5
job_runner.default_options["nodes"] = 1
htk.num_tasks = 12



usage = "usage: %prog [options] configfiles"
parser = OptionParser(usage=usage)
parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

config = SafeConfigParser({'name': 'EXPERIMENT NAME_TO_BE_FILLED!',
							'prefix': '',
							'minvariance': 0.05,
							'HERest_pruning': '300.0 500.0 2000.0'})
config.read(configs if len(configs) > 0 else "train_config")


current_step = 0
experiment_name = config.get('DEFAULT', 'name')
data_manipulation.createLogDirs()
target_hmm_dir = ""

# Data Collection step
if current_step >= options.step:
	dicts = []

	corpora = []
	
	cur_dict_id = 1
	while config.has_option("dict"+str(cur_dict_id), "location"):
		dicts.append([config.get("dict"+str(cur_dict_id), "location"),
						config.get("dict"+str(cur_dict_id), "prefix")])
		cur_dict_id += 1
	
	if len(dicts) == 0: sys.exit("No Dictionaries Found!")
	
	cur_corpus_id = 1
	while config.has_option("corpus"+str(cur_corpus_id), "location"):
		corpora.append([config.get("corpus"+str(cur_corpus_id), "location"),
						config.get("corpus"+str(cur_corpus_id), "prefix")])
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
	htk.HLEd(current_step, 'corpora/words.mlf', mkmono0_led, '*', 'files/monophones0', 'files/mono0.mlf', 'dictionary/dict')
	htk.HLEd(current_step, 'corpora/words.mlf', mkmono1_led, '*', 'files/monophones1', 'files/mono1.mlf', 'dictionary/dict')
	
	
current_step += 1 	

# Set some common variables
scpfile = 'corpora/train.scp'
configfile = 'config/config'
if not os.path.exists(scpfile): sys.exit("Not Found: " + scpfile)
if not os.path.exists(configfile): sys.exit("Not Found: " + configfile)

htk.default_config_file = configfile
htk.default_HERest_pruning = config.get("DEFAULT", "HERest_pruning").split(None, 2)

phones_list = 'files/monophones0'
transcriptions = 'files/mono0.mlf'



# Flat start step, calculate global variances with HCompV
if current_step >= options.step:
	source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
	
	protofile = 'config/proto'
	if not os.path.exists(protofile): sys.exit("Not Found: " + protofile)
	htk.HCompV(current_step, scpfile, target_hmm_dir, protofile, config.get('DEFAULT', 'minvariance'))
	
	data_manipulation.make_model_from_proto(target_hmm_dir, 'files/monophones0')


# Re estimate model 3 times
for i in range(0,3):
	current_step += 1

	if current_step >= options.step:
		source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
		
		htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
	

current_step += 1

# Introduce sp model by copying it from sil
if current_step >= options.step:
	source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
	
	data_manipulation.add_sp_to_phonelist(phones_list, 'files/monophones1')
	data_manipulation.copy_sil_to_sp(source_hmm_dir, target_hmm_dir)
	

phones_list = 'files/monophones1'
transcriptions = 'files/mono1.mlf'

current_step += 1

# Tie the middle sil state to the sp state
if current_step >= options.step:
	source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
	
	sil_hed = "config/sil.hed"
	if not os.path.exists(sil_hed): sys.exit("Not Found: " + sil_hed)
	
	htk.HHEd(current_step, source_hmm_dir, target_hmm_dir, sil_hed, phones_list)

	
# Re estimate model 2 times
for i in range(0,2):
	current_step += 1

	if current_step >= options.step:
		source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
		
		htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
	
transcriptions = 'files/mono1_aligned.mlf'

# same step still, realign data
if current_step >= options.step:
	data_manipulation.add_silence_to_dictionary('dictionary/dict', 'dictionary/dict_silence_')
	htk.HVite(current_step, scpfile, target_hmm_dir, 'dictionary/dict_silence_', phones_list, 'corpora/words.mlf', transcriptions)
	
	data_manipulation.filter_scp_by_mlf(scpfile, 'files/train.scp', transcriptions, 'files/excluded_utterances')
	
scpfile = 'files/train.scp'

# Re estimate model 2 times
for i in range(0,2):
	current_step += 1

	if current_step >= options.step:
		source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
		
		htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
	

current_step += 1

# Make triphone transcriptions and transform model to triphone
if current_step >= options.step:
	source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
	
	led_file = 'config/mktri.led'
	if not os.path.exists(led_file): sys.exit("Not Found: " + led_file)
	
	triphones_list = 'files/triphones'
	htk.HLEd(current_step, transcriptions, led_file, '*', triphones_list, 'files/tri.mlf')
	
	data_manipulation.make_tri_hed(triphones_list, 'files/mktri.hed')
	
	htk.HHEd(current_step, source_hmm_dir, target_hmm_dir, 'files/mktri.hed', phones_list)
	
phones_list = 'files/triphones'
transcriptions = 'files/tri.mlf'
	

# Re estimate model 2 times
for i in range(0,2):
	current_step += 1

	if current_step >= options.step:
		source_hmm_dir, target_hmm_dir = data_manipulation.createHmmDir(current_step)
		
		htk.HERest(current_step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions)
	

current_step += 1

if current_step >= options.step:
	data_manipulation.make_tree_hed([['../phonetic_rules._en', 'en_']], 'files/monophones1', 'files/tree.hed', 350.0, 1000.0, target_hmm_dir + '/stats', 'files/fulllist', 'files/tiedlist', 'files/trees')
print "Finished!"


