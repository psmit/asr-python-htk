#!/usr/bin/python

########################################################################
# job_runner.py
#
# Description:
# ------------
# This script will run an array job in the appropriate way. 
# The appropriate way is:
# - If run on the stimulus host it will submit the command with qsub
# - If run on the triton host it will submit the command with sbatch
# - Otherwise it will spawn threads to process the commands locally
#
# Type job_runner.py --help to get a list of options.
#
#
# Author: Peter Smit (peter@cis.hut.fi)
########################################################################
import sys
import os.path
import signal
from subprocess import *
from optparse import OptionParser
import re
import time
from socket import gethostname
import random

# The following modules are only needed when we run locally. Ignore if they are not present.
try:
	from multiprocessing import Queue
	from Queue import Empty

	import multiprocessing
	from multiprocessing import Process
except ImportError:
	pass


#global variables
verbosity = 0
runner = object

#default_options is only used when job_runner is used as module
default_options = {}

def submit_job(commandarr, extra_options = {}):
	global runner
	global default_options
	
	input_options = dict(default_options, **extra_options)
	
	parser = getOptParser()
	options = parser.parse_args(["dummy"])[0]
	
	for a,b in input_options.items():
		setattr(options,a,b)
		
	setNewRunner(options, commandarr)
	
	runner.run()
	

def main():
	global verbosity
	global runner
	
	#define command line options
	parser = getOptParser()
	
	(options, args) = parser.parse_args()
	verbosity = options.verbosity
	
	#check or at least a command is given
	if len(args) == 0:
		print "No command given!"
		sys.exit(10)
	
	setNewRunner(options, args)
	
	# Run our task
	runner.run()

def getOptParser():
	usage = "usage: %prog [options] -- command"
	parser = OptionParser(usage=usage)
	parser.add_option("-T", "--numtasks", type="int", dest="numtasks", help="Number of tasks to launch", default=1)
	parser.add_option("-t", "--timelimit", dest="timelimit", help="Timelimit for one task (in hh:mm:ss format)", default="00:15:00")
	parser.add_option("-m", "--memlimit", type="int", dest="memlimit", help="Memorylimit for one task (in MB)", default=100)
	parser.add_option("-o", "--output-stream", dest="ostream", help="write outputstream to FILE (%c for command, %j for id of first job, %J for real job id, %t for task id). If a directory is given, the default format is used in that directory", default="%c.o%j.%t", metavar="FILE")
	parser.add_option("-e", "--error-stream", dest="estream", help="write outputstream to FILE (%c for command, %j for id of first job, %J for real job id, %t for task id). If a directory is given, the default format is used in that directory", default="%c.e%j.%t", metavar="FILE")
	parser.add_option("-p", "--priority", type="int", dest="priority", help="Job priority. Higher priority is running later", default=0)
	parser.add_option("-q", "--queue", dest="queue", help="Queue, only used for GridEngine (stimulus) at the moment", default="-soft -q helli.q")
	parser.add_option("-c", "--cores", type="int", dest="cores", help="Number of cores to use (when running local). Negative numbers indicate the number of cores to keep free", default=-1)
	parser.add_option("-N", "--nodes", type="int", dest="nodes", help="Number of nodes to use (Triton)", default=1)
	parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="verbosity", default=0)
	return parser

def setNewRunner(options, args):
	global runner
	
	# Select runner class based on hostname
	hostname = gethostname()
	if hostname[0:(len("stimulus"))] == "stimulus":
		runner = StimulusRunner(options, args)
	elif hostname[0:(len("triton"))] == "triton":
		runner = TritonRunner(options, args)
	else:
		runner = LocalRunner(options, args)

#Base class with common functionality. Do not use inmediately but a sub-class instead
class Runner(object):
	options = []
	commandarr = []
	jobname = ""
	
	def __init__(self, options, commandarr):
		self.options = options
		
		# Prepend full path if local script is given for the command and the output streams
		if commandarr[0][0] != '.' and commandarr[0][0] != '/' and os.path.isfile(os.getcwd() + '/' + commandarr[0]):
			commandarr[0] = os.getcwd() + '/' + commandarr[0]
		
		if self.options.ostream[0] != '.' and self.options.ostream[0] != '/':
			self.options.ostream = os.getcwd() + '/' + self.options.ostream
			
		if self.options.estream[0] != '.' and self.options.estream[0] != '/':
			self.options.estream = os.getcwd() + '/' + self.options.estream
		
		# If the outputstreams are just directories, add the default filename pattern
		if os.path.isdir(self.options.ostream):
			self.options.ostream = self.options.ostream + '/%c.o%j.%t'
			
		if os.path.isdir(self.options.estream):
			self.options.estream = self.options.estream + '/%c.e%j.%t'
			
		self.commandarr = commandarr
		
		#create a nice job name
		self.jobname = os.path.basename(commandarr[0])
		
		# do some validations
		self.validate_options()
		
	def validate_options(self):
		# check time limit
		if not re.match('^[0-9]{2}:[0-9]{2}:[0-9]{2}$', self.options.timelimit):
			print "Time limit has not the correct syntax (hh:mm:ss). For example 48:00:00 for 2 days!"
			sys.exit(10)
	
	# Method for replacing the %t %j %J %c flags. Used for both output streams and commands
	def replace_flags(self, pattern, task, jobid_l = None, jobid_u = None):
		ret = pattern
		
		if type(ret).__name__=='list':
			ret = [str(item).replace('%t', str(task)) for item in ret]
		else:
			ret = ret.replace('%c', self.jobname)
			ret = ret.replace('%t', str(task))
			
			if jobid_l == None:
				ret = ret.replace('%j', '%J')
			else:
				ret = ret.replace('%j', str(jobid_l))
			
			if jobid_u != None:
				ret = ret.replace('%J', str(jobid_u))
		
		return ret
		

# Logic for running on the stimulus cluster
class StimulusRunner(Runner):
	def __init__(self, options, commandarr):
		super(StimulusRunner,self).__init__(options, commandarr)
	
	def run(self):
		global verbosity

		# Construct the qsub command
		batchcommand=['qsub']
		
		# Give a jobname
		batchcommand.extend(['-N', self.jobname ])
		
		# Set the timelimit and memory limit
		batchcommand.extend(['-l', 'mem='+str(self.options.memlimit)+'M,t='+self.options.timelimit])
		
		# If people want to be nice, we set a priority (Stimulus sees negative priority as nice)
		if self.options.priority > 0:
			batchcommand.append('-p='+str(-1 * self.options.priority))
		
			
		# Construct the filenames for the error and output stream
		outfile = self.replace_flags(self.options.ostream, "$TASK_ID", "$JOB_ID", "$JOB_ID")
		errorfile = self.replace_flags(self.options.estream, "$TASK_ID", "$JOB_ID", "$JOB_ID")
		
		real_command = self.replace_flags(self.commandarr, "$SGE_TASK_ID")
		
		# Set number of tasks
		batchcommand.extend(['-t', '1-'+str(self.options.numtasks)])
		
		# Set output streams
		batchcommand.extend(['-o', outfile, '-e', errorfile])
		batchcommand.extend(['-sync', 'y'])

		#Wrap it in a script file (Escaped)
		script = "#!/bin/bash\n" + "\"" + "\" \"".join(real_command) + "\""
		
		#Call the command. Feed in the script through STDIN and catch the result in output
		output = Popen(batchcommand, stdin=PIPE, stdout=PIPE).communicate(script)[0]
		
		if output.count("exited with exit code 0") < self.options.numtasks:
			if verbosity > 0:
				print str(output.count("exited with exit code 0")) + ' out of ' + str(self.options.numtasks) + ' tasks succeeded!'
			sys.exit(1)
		elif verbosity > 0:
			print 'All ' + str(self.options.numtasks) + ' tasks succeeded'
	
	def cancel(self):
		sys.exit(255)


# Logic for running on the Triton cluster
class TritonRunner(Runner):
	job = 0
	
	def __init__(self, options, commandarr):
		super(TritonRunner,self).__init__(options, commandarr)
		
	def run(self):
		global verbosity
		
		
		# submit tasks to sbatch
		self.sbatch_runner()
		
		# Start a job that waits until all our tasks are finished	
		Popen(['srun', '-t', '00:01:00', '--mem-per-cpu', '10', '--dependency=afterany:'+str(self.job), 'sleep', str(0)], stderr=PIPE).wait()
		
		# Fetch the error codes of our tasks
		result = Popen(['sacct', '-n', '--format=ExitCode,State', '-P', '-j', str(self.job)], stdout=PIPE).communicate()[0]
		
		# If there was any error take appropriate action
		if result.count('0:0|COMPLETED') < 1:
			if verbosity > 0:
				print "Some tasks failed"
			sys.exit(1)
		elif verbosity > 0:
			print 'All tasks succeeded'
		
	# Method for submitting one task to sbatch
	def sbatch_runner(self):
		global verbosity

		# Construct the sbatch command
		batchcommand=['sbatch']
		
		# Give a jobname
		batchcommand.extend(['-J', self.jobname])
		
		# Set the timelimit
		batchcommand.extend(['-t', self.options.timelimit])
		
		batchcommand.extend(['-N', str(self.options.nodes)])
		batchcommand.extend(['-n', str(self.options.nodes * 12)])
		
		# Set the memory limit
		batchcommand.append('--mem-per-cpu='+ str(self.options.memlimit))
		
		# If people want to be nice, we set a priority
		if self.options.priority > 0:
			batchcommand.append('--nice='+str(self.options.priority))
		
		
		batchcommand.append('tritonarray.py')
		
		batchcommand.extend(['-T', '1-'+str(self.options.numtasks)])
		batchcommand.extend(['-o', self.options.ostream])
		batchcommand.extend(['-e', self.options.estream])
		batchcommand.append('--')
		batchcommand.extend(self.commandarr)
		
		success = False
		
		while not success:
			#Call sbatch
			output = Popen(batchcommand, stdout=PIPE).communicate()[0]
			
			#Find the jobid on the end of the line
			m = re.search('[0-9]+$', output)
			if type(m).__name__ != 'NoneType':
				self.job = m.group(0)
				success = True
			else:
				time.sleep(2)
			
		if verbosity > 0:
			print 'Job id: '+ str(self.job)
	
	
	# Method for cancelling the Triton jobs
	def cancel(self):
		global verbosity
		cancelcommand=['scancel']
		cancelcommand.append(self.job)
		call(cancelcommand)
		if verbosity > 0:
			print 'Jobs are cancelled!'
		sys.exit(255)
		

# Class for running the command locally in multiple threads
class LocalRunner(Runner):
	job_id = 0
	num_cores = 1
	
	cancelled = False
	failed = False
	
	processes = []
	mainprocess = None
	
	verbosity
	
	def __init__(self, options, commandarr):
		super(LocalRunner,self).__init__(options, commandarr)

		
		if options.cores > 0:
			self.num_cores = options.cores
		else:
			self.num_cores = max(1, multiprocessing.cpu_count() + options.cores)
		
		self.verbosity = options.verbosity
		
		if options.verbosity > 1:
			print str(self.num_cores) + " cores are used"
		
		# We choose a random job_id. What would be better?
		self.job_id = random.randint(1, 9999)
		
		if options.verbosity > 0:
			print "Job id "+str(self.job_id)
		
		self.mainprocress = multiprocessing.current_process()
		
	def run(self):
		global verbosity
		if verbosity > 0:
			print "Running job " + str(self.job_id) + " locally"
		
		q = Queue()
		
		# add all tasks to queue
		for t in range(1,self.options.numtasks + 1):
			outfile = self.replace_flags(self.options.ostream, t, self.job_id, self.job_id)
			errorfile = self.replace_flags(self.options.estream, t, self.job_id, self.job_id)
			real_command = self.replace_flags(self.commandarr, t, self.job_id, self.job_id)
			c = [t, real_command, outfile, errorfile]
			q.put(c)
			
		# make appropriate number of processes to process queue
		for pnum in range(1,self.num_cores+1):
			p = Process(target=self.runFromQueue, args=(q,))
			p.start()
			self.processes.append(p)
		
		# Check every 3 seconds or the cancelled flag is set, or that the queue is empty
		while not q.empty() and not self.cancelled:
			time.sleep(3)
		
		print "Queue empty"
		
		# If cancel flag is set, terminate jobs
		if self.cancelled:
			print "Cancel now"
			self.cancel()
		
		# check or everything is ready (with processing)
		allready = False
		while not self.cancelled and not allready:
			allready = True
			for p in self.processes:
				p.join(1)
				if p.is_alive():
					allready = False
		
		print "After really ready"
		# Also the last jobs can have given a cancel, so do a cancel again
		if self.cancelled:
			self.cancel()
		
		# If failed act appropriately
		if(self.failed):
			sys.exit(1)
		
	def runFromQueue(self, q):
		global verbosity
		try:
			while not self.cancelled:
				command = q.get_nowait()
				if self.verbosity > 1:
					print "\tStart task " + str(command[0])
				of = open(command[2], 'w')
				ef = open(command[3], 'w')
				resultcode = Popen(command[1], stdout=of, stderr=ef).wait()
				of.close(); ef.close()
				
				if resultcode != 0:
					print "Task " + str(command[0]) + " failed with code "+ str(resultcode) +"!"
					self.cancelled = True
					self.failed = True
		except Empty:
			pass
		
	def cancel(self):
		if self.mainprocress == multiprocessing.current_process():
			self.cancelled = True
			try:
				for p in self.processes:
					p.terminate()
			except:
				pass
			if verbosity > 0:
				print 'Jobs are cancelled!'
			sys.exit(255)

def signal_handler(signal, frame):
	global verbosity
	global runner
	
	runner.cancel()
	
	if verbosity > 0:
		print 'Jobs are cancelled!'
	sys.exit(255)
	
#Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    main()
