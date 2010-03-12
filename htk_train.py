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
							'minvariance': 0.05})
config.read(configs if len(configs) > 0 else "train_config")


current_step = 0
experiment_name = config.get('DEFAULT', 'name')

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
	
	# Make phone transcriptions
	if not os.path.exists('config/mkmono.led'): sys.exit("Not Found: " + 'config/mkmono.led')
	if os.path.isdir('files'): shutil.rmtree('files')
	os.mkdir('files')
	htk.HLEd('dictionary/dict', 'corpora/words.mlf', 'config/mkmono.led', '*', 'files/monophones0', 'files/mono.mlf')
	
	
current_step += 1 	

scpfile = 'corpora/train.scp'
configfile = 'config/config'
if not os.path.exists(scpfile): sys.exit("Not Found: " + scpfile)
if not os.path.exists(configfile): sys.exit("Not Found: " + configfile)
htk.default_config_file = configfile

# Flat start step
if current_step >= options.step:
	target_hmm_dir = 'hmm%02d' % current_step
	
	protofile = 'config/proto'
	if not os.path.exists(protofile): sys.exit("Not Found: " + protofile)
	htk.HCompV(scpfile, target_hmm_dir, protofile, config.get('DEFAULT', 'minvariance'))
	
			
#scpfile = 'train.scp'
#source_hmm_dir = 'hmm02'
#target_hmm_dir = 'hmm03'
#phones_list = 'monophones0'
#transcriptions = 'mono.mlf'
#config = 'config'
#pruning = ["300.0", "500.0", "2000.0"]


#htk.HERest(scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, config, pruning)



#job_runner.default_options = {'numtasks': 20}

#job_runner.submit_job(['pwd'], {'verbosity': 2, 'numtasks':22})

print "Finished!"
