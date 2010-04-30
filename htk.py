#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-

import glob
import os
import job_runner
import shutil
import re

num_tasks = 100
extra_HTK_options = ["-A", "-D", "-V", "-T", "1"]

default_config_file = None
default_HERest_pruning = None

clean_scp_files = True
clean_old_logs = True
log_step = -1

def HDecode(step,  scpfile, model_dir, dict, phones_list, language_model,  label_dir, num_tokens, out_mlf, configs, lm_scale, beam, end_beam, max_pruning, adapt_dirs = []):
    global num_tasks, extra_HTK_options

    max_tasks = split_file(scpfile, num_tasks)

    HDecode = ["HDecode"]
    HDecode.extend(extra_HTK_options)

    for config in configs:
        HDecode.extend(['-C', config])

    for source_dir, extension in adapt_dirs:
        HDecode.extend(['-J', source_dir, extension])

    HDecode.extend(["-S", scpfile+ ".part.%t",
                "-H", model_dir + "/macros",
                "-H", model_dir + "/hmmdefs",
                '-z', 'lat',
                '-o', 'T',
                '-i', out_mlf+'.part.%t',
                '-l', label_dir,
                "-w", language_model,
                '-n', num_tokens,
                '-s', lm_scale,
                '-t', beam,
                '-v', end_beam,
                '-u', max_pruning,
                dict,
                phones_list])

    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job([str(part) for part in HDecode], {'numtasks': min(max_tasks, num_tasks),
                                    'ostream': ostream,
                                    'estream': estream,
                                    'memlimit': '2000',
                                    'timelimit': '06:00:00'} )

    merge_mlf_files(out_mlf)
    # remove splitted scp files
    clean_split_file(scpfile)

def lattice_rescore(step, lat_dir, lat_dir_out, lm, lm_scale):
    global num_tasks

    clean_split_dir(lat_dir_out)

    rescore = ["lattice-tool"]

    lattice_scp = lat_dir+'/lattices.scp'

    with open(lattice_scp, 'w') as lattice_scp_file:
        for lattice_file in glob.iglob(lat_dir + '/*.lat.gz'):
            print >> lattice_scp_file, lattice_file

    max_tasks = split_file(lattice_scp, num_tasks)

    rescore.extend(["-order", '10',
                    '-read-htk',
                    '-htk-lmscale', lm_scale,
                    '-in-lattice-list', lattice_scp+'.part.%t',
                    '-lm', lm,
                    '-out-lattice-dir', lat_dir_out+'.part.%t',
                    '-write-htk',
                    '-debug', '1'])

    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job([str(part) for part in rescore], {'numtasks': max_tasks,
                                    'ostream': ostream,
                                    'estream': estream})

    merge_split_dir(lat_dir_out)
    clean_split_file(lattice_scp)

def lattice_decode(step ,lat_dir, out_mlf, lm_scale):
    global num_tasks

    decode = ["lattice-tool"]

    lattice_scp = lat_dir+'/lattices.scp'

    with open(lattice_scp, 'w') as lattice_scp_file:
        for lattice_file in glob.iglob(lat_dir + '/*.lat.gz'):
            print >> lattice_scp_file, lattice_file

    max_tasks = split_file(lattice_scp, num_tasks)

    decode.extend(['-read-htk',
                    '-htk-lmscale', lm_scale,
                    '-in-lattice-list', lattice_scp+'.part.%t',
                    '-viterbi-decode'])

    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job([str(part) for part in decode], {'numtasks': max_tasks,
                                    'ostream': ostream,
                                    'estream': estream})
    r = re.compile('(?<=[^_>])[ ]')
    with open(out_mlf, 'w') as out_mlf_file:
        print >> out_mlf_file, "#!MLF!#"
        for file in glob.iglob(ostream.replace('%c', 'lattice-tool').replace('%t', '*').replace('%j', '*')):
            if file.endswith('parent'):
                continue
            for line in open(file):
                if line.startswith('#!MLF!#'):
                    continue
                else:
                    filename, transcription = line.split(None, 1)
                    transcription = transcription.replace(r'\344', u'ä'.encode('iso-8859-1')).replace(r'\366', u'ö'.encode('iso-8859-1'))
                    print >> out_mlf_file, '"*/%s.rec"' % os.path.splitext(os.path.basename(filename))[0]
                    transcription = r.sub('', transcription)
                    for word in transcription.split():
                        print >> out_mlf_file, word
                    print >> out_mlf_file, "."

    clean_split_file(lattice_scp)

def HLEd(step, input_transcriptions, led_file, selector, phones_list, output_transcriptions, dict = None):
    global num_tasks, extra_HTK_options
    HLEd = ["HLEd"]
    HLEd.extend(extra_HTK_options)
                    
    if dict:
        HLEd.extend(["-d", dict])
        
    HLEd.extend(["-n", phones_list,
                "-l", selector,
                "-i", output_transcriptions,
                led_file,
                input_transcriptions])

    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(HLEd, {'numtasks': 1,
                                    'ostream': ostream,
                                    'estream': estream})
                                    
                                    

def HCompV(step, scpfile, target_hmm_dir, protofile, min_variance, config = None):
    global num_tasks, extra_HTK_options, default_config_file
    
    if config is None: config = default_config_file
    
    HCompV = ["HCompV"]
    HCompV.extend(extra_HTK_options)
    HCompV.extend(["-C", config,
                "-f", min_variance,
                "-m",
                "-S", scpfile,
                "-M", target_hmm_dir,
                protofile])
    
    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(HCompV, {'numtasks': 1,
                                    'ostream': ostream,
                                    'estream': estream,
                                    'timelimit': '01:00:00'})            

def HERest_estimate_transform(step, scpfile, source_hmm_dir, target_dir, phones_list, transcriptions,  config, num_chars = 3, target_extension = 'cmllr', extra_source_dirs = [], pruning = None, min_mix_weigth = 0.1, prune_treshold = 20.0):
    global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning

    if config is None: config = default_config_file
    if pruning is None: pruning = default_HERest_pruning

    # divide scp files over HERest tasks
    max_tasks = split_file(scpfile, num_tasks, True, num_chars)

    HERest = ["HERest"]
    HERest.extend(extra_HTK_options)


    if type(config).__name__=='list':
        for c in config:
            HERest.extend(["-C", c])
    else:
        HERest.extend(["-C", config])

    pattern = "*/" + ('%' * num_chars) + "*.*" 

    HERest.extend(["-h", pattern,
                    "-I", transcriptions,
                    "-H", source_hmm_dir + "/macros",
                    "-H", source_hmm_dir + "/hmmdefs",
                    "-M", target_dir,
                    "-K", target_dir, target_extension,
                    "-J", source_hmm_dir + '/cmllr',
                    "-S", scpfile+ ".part.%t",
                    "-w", str(min_mix_weigth),
                    "-m", '0',
                    "-u", "a",
                    "-c", str(prune_treshold)])

    for source_dir, extension in extra_source_dirs:
        HERest.extend(['-J', source_dir, extension])


    HERest.extend(["-t"])
    HERest.extend(pruning)

    HERest.extend([phones_list])

    ostream, estream = _get_output_stream_names(step)

    job_runner.submit_job(HERest, {'numtasks': min(max_tasks, num_tasks),
                                    'ostream': ostream,
                                    'estream': estream} )

    # remove splitted scp files
    clean_split_file(scpfile)


def HERest(step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, stats = False, config = None, transform_dir = None, num_pattern_chars = 3, pruning = None, binary = True):
    global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning
    
    if config is None: config = default_config_file
    if pruning is None: pruning = default_HERest_pruning
    
    # divide scp files over HERest tasks
    max_tasks = split_file(scpfile, num_tasks, transform_dir is None)

    HERest = ["HERest"]
    HERest.extend(extra_HTK_options)


    if type(config).__name__=='list':
        for c in config:
            HERest.extend(["-C", c])
    else:
        HERest.extend(["-C", config])

    HERest.extend(["-I", transcriptions,
                    "-H", source_hmm_dir + "/macros",
                    "-H", source_hmm_dir + "/hmmdefs",
                    "-M", target_hmm_dir])

    if transform_dir is not None:
        pattern = "*/" + ('%' * num_pattern_chars) + "*.*"
        HERest.extend(["-J", transform_dir, 'cmllr',
                    "-E", transform_dir, 'cmllr',
                    "-h", pattern])
    
    HERest.extend(["-t"])
    HERest.extend(pruning)
    
    # copy merge_command now because the last options are different
    HERest_merge = list(HERest)
    
    HERest.extend(["-S", scpfile+ ".part.%t",
                    "-p", "%t",
                    phones_list])
    
    ostream, estream = _get_output_stream_names(step)
    
    job_runner.submit_job(HERest, {'numtasks': min(max_tasks, num_tasks),
                                    'ostream': ostream,
                                    'estream': estream,
                                    'priority': 1} )
    
    if stats:
        HERest_merge.extend(["-s", target_hmm_dir + "/stats"])

    if binary:
        HERest_merge.extend(["-B"])
        
    HERest_merge.extend(["-p", str(0),
                        phones_list])
    HERest_merge.extend(glob.glob(target_hmm_dir+"/*.acc"))
    
    job_runner.submit_job(HERest_merge,  {'numtasks': 1,
                                    'ostream': ostream,
                                    'estream': estream})

    # remove acc files
    for file in glob.glob(target_hmm_dir+"/*.acc"): os.remove(file)
    
    # remove splitted scp files
    clean_split_file(scpfile)
    
    
def HHEd(step, source_hmm_dir, target_hmm_dir, hed, phones_list, w_flag = None):
    global extra_HTK_options
    
    HHEd = ["HHEd"]
    HHEd.extend(extra_HTK_options)
    HHEd.extend(["-H", source_hmm_dir + "/macros",
                "-H", source_hmm_dir + "/hmmdefs",
                "-M", target_hmm_dir])

    if w_flag is not None:
        HHEd.extend(['-w', w_flag])


    HHEd.extend([hed,
                phones_list])
    
    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(HHEd, {'numtasks': 1,
                                    'ostream': ostream,
                                    'estream': estream})
                                    
def HVite(step, scpfile, hmm_dir, dict, phones_list, word_transcriptions, new_transcriptions, config = None, pruning = None):
    global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning
    
    if config is None: config = default_config_file
    if pruning is None: pruning = default_HERest_pruning
    
    # divide scp files over HERest tasks
    split_file(scpfile, num_tasks)
    
    HVite = ["HVite"]
    HVite.extend(extra_HTK_options)

    HVite.extend(["-S", scpfile+ ".part.%t",
                    "-i", new_transcriptions + ".part.%t", 
                    "-l", '*',
                    "-C", config,
                    "-o", "ST",
                    "-a",
                    "-H", hmm_dir + "/macros",
                    "-H", hmm_dir + "/hmmdefs",
                    "-m",
                    "-y", "lab",
                    "-I", word_transcriptions])
    
    HVite.extend(["-t"])
    HVite.extend(pruning)
    
    HVite.extend([dict,
                phones_list])
    
    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(HVite, {'numtasks': num_tasks,
                                    'ostream': ostream,
                                    'estream': estream})
                                    
    with open(new_transcriptions, 'w') as mlffile:
        print >> mlffile, '#!MLF!#'
        for file in glob.glob(new_transcriptions+".part.*"):
            for line in open(file):
                if not line.startswith('#!MLF!#'): 
                    print >> mlffile, line.rstrip()
            os.remove(file)
    
    clean_split_file(scpfile)
    
                                                
def HCopy(step, scp_file, config):
    global num_tasks, extra_HTK_options
    
    split_file(scp_file, num_tasks)
    
    HCopy = ["HCopy"]
    HCopy.extend(extra_HTK_options)
    HCopy.extend(["-C", config,
                "-S", scp_file+ ".part.%t"])
    
    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(HCopy, {'numtasks': num_tasks,
                                    'ostream': ostream,
                                    'estream': estream})    
                                    
    clean_split_file(scp_file)
    
def recode_audio(step, scp_file, data_set, amr):
    global num_tasks

    split_file(scp_file, num_tasks)
    recode_audio = ["recode_audio.py"]
    recode_audio.extend(["-s", data_set,
                         "-S", scp_file+ ".part.%t"])
    if amr:
        recode_audio.append('-a')
        
    ostream, estream = _get_output_stream_names(step)
    job_runner.submit_job(recode_audio, {'numtasks': num_tasks,
                                    'ostream': ostream,
                                    'estream': estream})

    clean_split_file(scp_file)

def _get_output_stream_names(step):
    global clean_old_logs, log_step
    
    if clean_old_logs and step != log_step:
        for file in glob.glob('log/tasks/%03d.*' % step): os.remove(file)
        
    log_step = step
    return ('log/tasks/%03d.%%c.o%%j.%%t' % step, 'log/tasks/%03d.%%c.e%%j.%%t' % step)
    
    
def split_file(file_name, parts, keep_speaker_together = False, num_speaker_chars = 3):
    target_files = [open(name, 'w') for name in [file_name + ".part." + str(i) for i in range(1,parts+1)]]

    real_num_parts = 0

    source_file = open(file_name)
    if not keep_speaker_together:
        counter = 0
        for line in source_file:
            target_files[counter].write(line)
            real_num_parts = max(counter, real_num_parts)
            counter = (counter + 1)%parts
    else:
        prev_speaker = ''
        counter = -1
        for line in source_file:
            cur_speaker = os.path.basename(line.rstrip())[:num_speaker_chars]

            if prev_speaker != cur_speaker:
                prev_speaker = cur_speaker
                counter = (counter + 1)%parts
                real_num_parts = max(counter, real_num_parts)
            target_files[counter].write(line)

    
    for file in target_files: file.close()
    return real_num_parts + 1

def clean_split_dir(dir_prefix):
    for dir in glob.iglob(dir_prefix+".part.*"): shutil.rmtree(dir)

def merge_split_dir(dir_prefix):
    if os.path.exists(dir_prefix): shutil.rmtree(dir_prefix)
    os.mkdir(dir_prefix)
    for dir in glob.iglob(dir_prefix+".part.*"):
        for file in glob.iglob(dir+"/*"):
            shutil.move(file, dir_prefix)

    clean_split_dir(dir_prefix)

def clean_split_file(file_name):
    global clean_scp_files
    if clean_scp_files:
        for file in glob.iglob(file_name+".part.*"): os.remove(file)

def merge_mlf_files(file_name):
    with open(file_name, 'w') as out_file:
        print >> out_file, "#!MLF!#"
        for in_file_name in glob.iglob(file_name+".part.*"):
            for line in open(in_file_name):
                if not line.startswith("#!MLF!#"):
                    print >> out_file, line.rstrip()
    clean_split_file(file_name)