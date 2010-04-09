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
import shutil

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
parser.add_option("-s", "--step", type="int", dest="step",help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity", default=1)
parser.add_option("-D", "--no-wav-delete", action="store_false", dest="delete_wav", default=True, help="Do not delete intermediate wav files")

options, configs = parser.parse_args()

config = SafeConfigParser({'train_set': 'train',
                            'eval_set': 'eval',
                            'devel_set': 'devel'})
config.read(configs if len(configs) > 0 else "create_mfcc_config")


logger.info("Starting step: %d" % options.step)
current_step = 0

raw_to_wav_list = 'raw2wav.scp'
wav_to_mfc_list = 'wav2mfc.scp'

if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Collect data file names'))
    if os.path.exists('wav'): shutil.rmtree('wav')
    if os.path.exists('mfc'): shutil.rmtree('mfc')

    if not config.has_option("audiofiles", "location") or not config.has_option("audiofiles", "type"):
        sys.exit("Configuration is not valid")

    waveforms = {}

    if os.path.exists('hcopy.scp'):
        os.remove('hcopy.scp')
    if config.get("audiofiles", "type") == 'speecon':
        for dset in ['train', 'eval', 'devel']:
            waveforms[dset] = data_manipulation.speecon_fi_selection(config.get("audiofiles", "location"), config.get("audiofiles", dset+"_set"))

    if config.get("audiofiles", "type") == 'wsj':
        locations = [os.path.join(config.get("audiofiles", "location"), 'wsj0'),
                     os.path.join(config.get("audiofiles", "location"), 'wsj1', 'wsj1')]

        for dset in ['train', 'eval', 'devel']:
            waveforms[dset] = data_manipulation.wsj_selection(locations, config.get("audiofiles", dset+"_set"))

    data_manipulation.create_scp_lists(waveforms, raw_to_wav_list, wav_to_mfc_list)



current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Creating wav files'))
    use_amr = False
    if config.has_option('amr', 'do_encode_decode') and config.getboolean('amr', 'do_encode_decode'):
        use_amr = True
    htk.recode_audio(current_step, raw_to_wav_list, config.get("audiofiles", "type"), use_amr)


current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'HCopying everything'))
    if not os.path.exists('config.hcopy'):
        sys.exit('File config.hcopy missing!')    
    htk.HCopy(current_step, wav_to_mfc_list, 'config.hcopy')

    os.unlink('raw2wav.scp')
    os.unlink('wav2mfc.scp')

current_step += 1
if current_step >= options.step:
    if options.delete_wav:
        logger.info("Start step: %d (%s)" % (current_step, 'Deleting intermediate wav files'))
        if os.path.exists('wav'): shutil.rmtree('wav')
    

current_step += 1
if current_step >= options.step:
    logger.info("Start step: %d (%s)" % (current_step, 'Making transcription file'))

    if config.get("audiofiles", "type") == 'speecon':
        data_manipulation.create_wordtranscriptions_speecon(['train.scp'],config.get('audiofiles', 'location'), 'words.mlf')
    #, 'devel.scp', 'eval.scp'
    if config.get("audiofiles", "type") == 'wsj':
        locations = [os.path.join(config.get("audiofiles", "location"), 'wsj0'),
                     os.path.join(config.get("audiofiles", "location"), 'wsj1', 'wsj1')]
        data_manipulation.create_wordtranscriptions_wsj(['train.scp', 'devel.scp', 'eval.scp'],locations, 'words.mlf')



print "Finished!"
