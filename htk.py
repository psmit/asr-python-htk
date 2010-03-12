#!/usr/bin/python

import glob
import os
import job_runner

num_tasks = 100
extra_HTK_options = ["-A", "-D", "-V", "-T", "1"]

default_config_file = None
default_HERest_pruning = None

def HLEd(dict, word_transcriptions, ledfile, selector, phones_list, phone_transcriptions):
	global num_tasks, extra_HTK_options
	HLEd = ["HLEd"]
	HLEd.extend(extra_HTK_options)
	HLEd.extend(["-d", dict,
				"-n", phones_list,
				"-l", selector,
				"-i", phone_transcriptions,
				ledfile,
				word_transcriptions])
	
	job_runner.submit_job(HLEd, 1)

def HCompV(scpfile, target_hmm_dir, protofile, min_variance, config = None):
	global num_tasks, extra_HTK_options, default_config_file
	
	if config == None: config = default_config_file
	
	HCompV = ["HCompV"]
	HCompV.extend(extra_HTK_options)
	HCompV.extend(["-C", config,
				"-f", min_variance,
				"-m",
				"-S", scpfile,
				"-M", target_hmm_dir,
				protofile])
	
	job_runner.submit_job(HCompV, 1)			
	
def HERest(scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, config = None, pruning = None):
	global num_tasks, extra_HTK_options, default_config_file, default_HERest_pruning
	
	if config == None: config = default_config_file
	if pruning == None: pruning = default_HERest_pruning
	
	# divide scp files over HERest tasks
	split_file(scpfile, num_tasks)
	
	HERest = ["HERest"]
	HERest.extend(extra_HTK_options)
	
	HERest.extend(["-C", config,
					"-I", transcriptions,
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
	
	
	job_runner.submit_job(HERest, num_tasks)
	
	HERest_merge.extend(["-p", str(0),
						phones_list])
	HERest_merge.extend(glob.glob(target_hmm_dir+"/*.acc"))
	
	job_runner.submit_job(HERest_merge, 1)

	# remove acc files
	for file in glob.glob(target_hmm_dir+"/*.acc"): os.remove(file)
	
	# remove splitted scp files
	clean_split_file(scpfile)
	

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

def clean_split_file(filename):
	for file in glob.glob(filename+".part.*"): os.remove(file)
