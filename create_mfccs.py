#!/usr/bin/env python2.6
# Usage: Run this script in the directory where it is working. Standard it searches a file create_mfcc_config. Other configuration file can be given as arguments

#import locale
#locale.setlocale(locale.LC_ALL, ('en', 'iso-8859-1'))

import data_manipulation
import job_runner
import htk
import htk_logger
import gather_wsj

import os
import os.path
import sys

from ConfigParser import SafeConfigParser
from optparse import OptionParser
import shutil

data_manipulation.create_log_dirs()
htk_logger.create_logger('create_mfcc', 'log/create_mfcc.log')

logger = htk_logger.logger

logger.info("Start create_mfcc")

job_runner.default_options["verbosity"] = 1

job_runner.default_options["timelimit"] = '04:00:00'
job_runner.default_options["memlimit"] = 500



usage = "usage: %prog [options] configfiles"
parser = OptionParser(usage=usage)
parser.add_option("-n", "--num-tasks", type="int", dest="numtasks",help="Number of different tasks", default=50)
parser.add_option("-s", "--step", type="int", dest="step",help="Starting step", default=0)
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity", default=1)
parser.add_option("-D", "--no-wav-delete", action="store_false", dest="delete_wav", default=True, help="Do not delete intermediate wav files")
parser.add_option("-p", "--priority", type="int", dest="priority", help="priority (more is worse)",     default=0)
parser.add_option('-x', '--exclude-nodes', dest="exclude_nodes", help="Triton nodes to exclude", default="")

options, configs = parser.parse_args()

htk.num_tasks = options.numtasks
job_runner.default_options["exclude_nodes"] = options.exclude_nodes
job_runner.default_options["priority"] = options.priority

if not options.delete_wav:
    htk.clean_scp_files = False

config = SafeConfigParser({'train_set': 'train',
                            'eval_set': 'eval',
                            'devel_set': 'devel',
                            'lang': 'Eng',
                            'selection': 'FM',
                            'extension': 'FI0',
                            })
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

    waveforms = {'train': [], 'eval': [], 'devel': []}

    if os.path.exists('hcopy.scp'):
        os.remove('hcopy.scp')
    if config.get("audiofiles", "type") == 'speecon':
        for dset in ['train', 'eval', 'devel']:
            waveforms[dset] = data_manipulation.speecon_fi_selection(config.get("audiofiles", "location"), config.get("audiofiles", dset+"_set"), config.get("audiofiles", "extension"))

    if config.get("audiofiles", "type") == 'wsj' or config.get("audiofiles", "type") == 'wsjcam':
        if os.path.exists('wsj_gather'):
            shutil.rmtree('wsj_gather')
        os.mkdir('wsj_gather')

        location = config.get("audiofiles", "location")

        for dset in ['train', 'eval', 'devel']:
            vocab = ""
            if config.has_option("audiofiles", dset+"_vocab"):
                vocab = config.get("audiofiles", dset+"_vocab")
            gather_wsj.gather(config.get("audiofiles", "location"),'wsj_gather', dset, vocab, [config.get("audiofiles", dset+"_set")])
            waveforms[dset] = sorted(set([p.rstrip() for p in open('wsj_gather/%s.scp'%dset)]))
            #waveforms[dset] = data_manipulation.wsj_selection(locations, config.get("audiofiles", dset+"_set"))

#    if config.get("audiofiles", "type") == 'wsjcam':
#        waveforms['train'] = data_manipulation.wsjcam_selection(config.get("audiofiles", "location"), 'si_tr')
#        waveforms['eval'] = data_manipulation.wsjcam_selection(config.get("audiofiles", "location"), 'si_et_20k')

    if config.get("audiofiles", "type") == 'dsp_eng':
        waveforms['train'] = data_manipulation.dsp_eng_selection(config.get("audiofiles", "location"))

    if config.get("audiofiles", "type") == 'bl_eng':
        waveforms['eval'] = data_manipulation.bl_eng_selection(config.get("audiofiles", "location"))

    if config.get("audiofiles", "type") == 'ued_bl':
        waveforms['train'] = data_manipulation.ued_bl_selection(config.get("audiofiles", "location"), [config.get("audiofiles", "lang")], config.get("audiofiles", "selection").lstrip().rstrip().split(','), 'train')
        waveforms['eval'] = data_manipulation.ued_bl_selection(config.get("audiofiles", "location"), [config.get("audiofiles", "lang")], config.get("audiofiles", "selection").lstrip().rstrip().split(','), 'eval')

    exclude_list = None
    if config.has_option("audiofiles", "exclude_list"):
        exclude_list = config.get("audiofiles", "exclude_list")
    data_manipulation.create_scp_lists(waveforms, raw_to_wav_list, wav_to_mfc_list, exclude_list)



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
        data_manipulation.create_wordtranscriptions_speecon(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')


    if config.get("audiofiles", "type") == 'wsj' or config.get("audiofiles", "type") == 'wsjcam':
        transcriptions = {}
        for dset in ['train', 'devel', 'eval']:
            transcriptions.update(data_manipulation.read_mlf('wsj_gather/%s.mlf' % dset, True))

        data_manipulation.write_mlf(transcriptions, 'words.mlf', 'mfc', True)

#    if config.get("audiofiles", "type") == 'wsj':
#        locations = [os.path.join(config.get("audiofiles", "location"), 'wsj0'),
#                     os.path.join(config.get("audiofiles", "location"), 'wsj1', 'wsj1')]
#        data_manipulation.create_wordtranscriptions_wsj(['train.scp', 'devel.scp', 'eval.scp'],locations, 'words.mlf')
#
#    if config.get("audiofiles", "type") == 'wsjcam':
#        data_manipulation.create_wordtranscriptions_wsjcam(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')

    if config.get("audiofiles", "type") == 'dsp_eng':
        data_manipulation.create_wordtranscriptions_dsp_eng(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')

    if config.get("audiofiles", "type") == 'bl_eng':
        data_manipulation.create_wordtranscriptions_bl_eng(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')

    if config.get("audiofiles", "type") == 'ued_bl':
        data_manipulation.create_wordtranscriptions_ued_bl(['train.scp', 'devel.scp', 'eval.scp'],config.get('audiofiles', 'location'), 'words.mlf')




print "Finished!"
