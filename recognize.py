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

from ConfigParser import SafeConfigParser
from optparse import OptionParser

if not os.path.exists('log'): os.mkdir('log')
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
parser.add_option("-m", "--model-iteration",      type="string", dest="model",      help="Starting step", default="hmm61")
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

job_runner.default_options["nodes"] = options.nodes
htk.num_tasks = options.nodes * 48

config = SafeConfigParser({'name': 'EXPERIMENT NAME_TO_BE_FILLED!',
                            'speaker_name_width': 5})
config.read(configs if len(configs) > 0 else "recognition_config")



if not config.has_option('model', 'model_dir') or not config.has_option('model', 'config'):
    sys.exit("Please give more configuration")


scp_file = config.get('model', 'model_dir') + '/files/eval.scp'
model = config.get('model', 'model_dir') + '/' + options.model
adapt_dir = model + "/cmllr"
lm = config.get('model', 'lm')
config_hdecode = config.get('model', 'config')
label_dir = 'label_dir'
num_tokens = 0
lm_scale = 12.0
beam = 170.0
end_beam = 113.0
max_pruning = 40000


htk.HDecode(1, scp_file, model, lm, label_dir, num_tokens, [config, config_hdecode], lm_scale, beam, end_beam, max_pruning, adapt_dir)


