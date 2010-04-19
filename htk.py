#!/usr/bin/env python2.6

import glob
import os
import job_runner

num_tasks = 100
extra_HTK_options = ["-A", "-D", "-V", "-T", "1"]

default_config_file = None
default_HERest_pruning = None

clean_scp_files = True
clean_old_logs = True
log_step = -1

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

def HERest_estimate_transform(step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions,  config, num_chars = 3, pruning = None, min_mix_weigth = 0, prune_treshold = 20.0):
    global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning

    if config is None: config = default_config_file
    if pruning is None: pruning = default_HERest_pruning

    # divide scp files over HERest tasks
    max_tasks = split_file(scpfile, num_tasks, True)

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
                    "-M", target_hmm_dir,
                    "-S", scpfile+ ".part.%t",
                    "-w", min_mix_weigth,
                    "-m", 0,
                    "-u", "a",
                    "-c", prune_treshold])


    HERest.extend(["-t"])
    HERest.extend(pruning)

    HERest.extend([phones_list])

    ostream, estream = _get_output_stream_names(step)

    job_runner.submit_job(HERest, {'numtasks': min(max_tasks, num_tasks),
                                    'ostream': ostream,
                                    'estream': estream} )

    # remove splitted scp files
    clean_split_file(scpfile)


def HERest(step, scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, stats = False, config = None, pruning = None):
    global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning
    
    if config is None: config = default_config_file
    if pruning is None: pruning = default_HERest_pruning
    
    # divide scp files over HERest tasks
    split_file(scpfile, num_tasks)

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

    
    HERest.extend(["-t"])
    HERest.extend(pruning)
    
    # copy merge_command now because the last options are different
    HERest_merge = list(HERest)
    
    HERest.extend(["-S", scpfile+ ".part.%t",
                    "-p", "%t",
                    phones_list])
    
    ostream, estream = _get_output_stream_names(step)
    
    job_runner.submit_job(HERest, {'numtasks': num_tasks,
                                    'ostream': ostream,
                                    'estream': estream} )
    
    if stats:
        HERest_merge.extend(["-s", target_hmm_dir + "/stats"])
        
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

            if prev_speaker is not cur_speaker:
                counter = (counter + 1)%parts
                real_num_parts = max(counter, real_num_parts)
            target_files[counter].write(line)

    
    for file in target_files: file.close()
    return real_num_parts

def clean_split_file(file_name):
    global clean_scp_files
    if clean_scp_files:
        for file in glob.glob(file_name+".part.*"): os.remove(file)
