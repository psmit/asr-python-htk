#!/usr/bin/python

import glob
import os
import job_runner

num_tasks = 100
extra_HTK_options = ["-A", "-D", "-V", "-T", "1"]

default_config_file = None
default_HERest_pruning = None



def HERest(scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, config = None, pruning = None):
	global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning
	
	if config == None: config = default_config_file
	if pruning == None: pruning = default_HERest_pruning
	
	# divide scp files over HERest tasks
	split_file(scpfile, num_tasks)
	
	command = ["HERest"]
	command.extend(extra_HTK_options)
	
	command.extend(["-C", config])
	command.extend(["-I", transcriptions])
	command.extend(["-t"])
	command.extend(pruning)
	command.extend(["-H", source_hmm_dir + "/macros"])
	command.extend(["-H", source_hmm_dir + "/hmmdefs"])
	command.extend(["-M", target_hmm_dir])
	
	# copy merge_command now because the last options are different
	merge_command = list(command)
	
	command.extend(["-S", scpfile+ ".part.%t"])
	command.extend(["-p", "%t"])
	command.append(phones_list)
	
	job_runner.submit_job(command, {"numtasks": num_tasks})
	
	merge_command.extend(["-p", str(0)])
	merge_command.append(phones_list)
	merge_command.extend(glob.glob(target_hmm_dir+"/*.acc"))
	
	job_runner.submit_job(merge_command, {"numtasks": 1})

	# remove acc files
	for file in glob.glob(target_hmm_dir+"/*.acc"): os.remove(file)
	
	# remove splitted scp files
	for file in glob.glob(scpfile+".part.*"): os.remove(file)
	
	
def HCopy(scpfile, config):
	global num_tasks, extra_HTK_options
	
	split_file(scpfile, num_tasks)
	
	command = ["HCopy"]
	command.extend(extra_HTK_options)
	
	command.extend(["-C", config])
	command.extend(["-S", scpfile+ ".part.%t"])
	
	job_runner.submit_job(command, {"numtasks": num_tasks})
	
	for file in glob.glob(scpfile+".part.*"): shutil.rm(file)
	
def split_file(filename, parts):
	targetfilenames = [filename + ".part." + str(i) for i in range(1,parts+1)]
	targetfiles = [open(fname, 'w') for fname in targetfilenames]
	
	sourcefile = open(filename)
	counter = 0
	for line in sourcefile:
		targetfiles[counter].write(line)
		counter = (counter + 1)%parts
	
	for f in targetfiles: f.close()
