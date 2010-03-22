#!/usr/bin/env python2.6
# Usage: Run this script in the directory where it is working. Standard it searches a file create_mfcc_config. Other configuration file can be given as arguments

import data_manipulation
import job_runner
import htk
import htk_logger

import os
import os.path
import sys

from ConfigParser import SafeConfigParser
from optparse import OptionParser

if not os.path.exists('log'): os.mkdir('log')
if not os.path.exists('log/tasks'): os.mkdir('log/tasks')
htk_logger.create_logger('create_mfcc', 'log/create_mfcc.log')

logger = htk_logger.logger

logger.info("Start create_mfcc")

job_runner.default_options["verbosity"] = 1
job_runner.default_options["nodes"] = 1
job_runner.default_options["timelimit"] = '04:00:00'
job_runner.default_options["memlimit"] = 500

htk.num_tasks = 48

usage = "usage: %prog [options] configfiles"
parser = OptionParser(usage=usage)
parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
options, configs = parser.parse_args()

config = SafeConfigParser({})
config.read(configs if len(configs) > 0 else "create_mfcc_config")


logger.info("Starting step: %d" % options.step)
current_step = 0

if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Data collection'))
    if not config.has_option("audiofiles", "location") or not config.has_option("audiofiles", "type"):
        sys.exit("Configuration is not valid")

	if os.path.exists('hcopy.scp'): os.remove('hcopy.scp')
    if config.get("audiofiles", "type") == 'speecon':
        data_manipulation.create_scp_lists_speecon(config.get("audiofiles", "location"))
        
    if config.get("audiofiles", "type") == 'wsj':
        data_manipulation.create_scp_lists_wsj(config.get("audiofiles", "location"))


current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'HCopying everything'))
    htk.HCopy(1, 'hcopy.scp', 'config.hcopy')

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Making words.mlf'))

    if config.get("audiofiles", "type") == 'speecon':
        data_manipulation.create_wordtranscriptions_speecon(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')

    if config.get("audiofiles", "type") == 'wsj':
        sys.exit("Not implemented for wsj")



print "Finished!"
