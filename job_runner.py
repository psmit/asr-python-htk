#!/usr/bin/python
import sys
import os.path
import signal
from subprocess import *
from optparse import OptionParser
import re
import time
from socket import gethostname

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


def main():
	global verbosity
	global runner
	
	#define command line options
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
	parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="verbosity", default=0)
	
	(options, args) = parser.parse_args()
	verbosity = options.verbosity
	
	#check or at least a command is given
	if len(args) == 0:
		print "No command given!"
		sys.exit(10)
	
	# Select runner class based on hostname
	hostname = gethostname()
	if hostname[0:(len("stimulus"))] == "stimulus":
		runner = StimulusRunner(options, args)
	elif hostname[0:(len("triton"))] == "triton":
		runner = TritonRunner(options, args)
	else:
		runner = LocalRunner(options, args)
	
	# Run our task
	runner.run()

#Base class with common functionality
class Runner(object):
	options = []
	commandarr = []
	jobname = ""
	
	def __init__(self, options, commandarr):
		self.options = options
		
		# prepend full path if local script is given
		if commandarr[0][0] != '.' and commandarr[0][0] != '/' and os.path.isfile(os.getcwd() + '/' + commandarr[0]):
			commandarr[0] = os.getcwd() + '/' + commandarr[0]
		
		if self.options.ostream[0] != '.' and self.options.ostream[0] != '/':
			self.options.ostream = os.getcwd() + '/' + self.options.ostream
			
		if self.options.estream[0] != '.' and self.options.estream[0] != '/':
			self.options.estream = os.getcwd() + '/' + self.options.estream
		
		if os.path.isdir(self.options.ostream):
			self.options.ostream = self.options.ostream + '/%c.o%j.%t'
			
		if os.path.isdir(self.options.estream):
			self.options.estream = self.options.estream + '/%c.e%j.%t'
			
		self.commandarr = commandarr
		#create a nice job name
		self.jobname = os.path.basename(commandarr[0])
		
		self.validate_options()
		
	def validate_options(self):
		# check time limit
		if not re.match('^[0-9]{2}:[0-9]{2}:[0-9]{2}$', self.options.timelimit):
			print "Time limit has not the correct syntax (hh:mm:ss). For example 48:00:00 for 2 days!"
			sys.exit(10)
		
	def replace_flags(self, pattern, task, jobid_l = None, jobid_u = None):
		ret = pattern
		
		if type(ret).__name__=='list':
			ret = [item.replace('%t', str(task)) for item in ret]
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
		

class StimulusRunner(Runner):
	def __init__(self, options, commandarr):
		super(StimulusRunner,self).__init__(options, commandarr)
	
	def run(self):
		##TODO this is the triton code
		global verbosity

		# Construct the sbatch command
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
		
		batchcommand.extend(['-t', '1-'+str(self.options.numtasks)])
		
		batchcommand.extend(['-o', outfile, '-e', errorfile])
		batchcommand.extend(['-sync', 'y'])
		
		
		
		#batchcommand.append('-')

		#Wrap it in a script file (Escaped)
		script = "#!/bin/bash\n" + "\"" + "\" \"".join(real_command) + "\""
		
		print ' '.join(batchcommand)
		#Call sbatch. Feed in the script through STDIN and catch the result in output
		output = Popen(batchcommand, stdin=PIPE, stdout=PIPE).communicate(script)[0]
		
		print output
		#Find the jobid on the end of the line
		#m = re.search('[0-9]+$', output)
		#self.jobs.append(m.group(0))
		#if verbosity > 1:
		#	print 'Task ' + str(task) + ' is submitted as job ' + m.group(0)
	
	def cancel(self):
		print "stimulus cancel"

class TritonRunner(Runner):
	jobs = []
	
	def __init__(self, options, commandarr):
		super(TritonRunner,self).__init__(options, commandarr)
		
	def run(self):
		global verbosity
		# submit tasks to sbatch
		for t in range(1,self.options.numtasks + 1):
			self.sbatch_runner(t)
		
		# Start a job that waits until all our tasks are finished	
		Popen(['srun', '-t', '00:01:00', '--mem-per-cpu', '10', '--dependency=afterany:'+':'.join(self.jobs), 'sleep', str(0)], stderr=PIPE).wait()
		
		# Fetch the error codes of our tasks
		result = Popen(['sacct', '-n', '--format=ExitCode', '-P', '-j', ','.join(self.jobs)], stdout=PIPE).communicate()[0]
		
		# If there was any error take appropriate action
		if result.count('0:0') < len(self.jobs):
			if verbosity > 0:
				print str(result.count('0:0')) + ' out of ' + str(len(self.jobs)) + ' tasks succeeded!'
			sys.exit(1)
		elif verbosity > 0:
			print 'All ' + str(len(self.jobs)) + ' tasks succeeded'
		
	def sbatch_runner(self, task):
		global verbosity

		# Construct the sbatch command
		batchcommand=['sbatch']
		
		# Give a jobname
		batchcommand.extend(['-J', self.jobname + '.' + str(task)])
		
		# Set the timelimit
		batchcommand.extend(['-t', self.options.timelimit])
		
		# Set the memory limit
		batchcommand.append('--mem-per-cpu='+ str(self.options.memlimit))
		
		# If people want to be nice, we set a priority
		if self.options.priority > 0:
			batchcommand.append('--nice='+str(self.options.priority))
		
		jobid = None
		if len(self.jobs) > 0:
			jobid = jobs[0]
			
		# Construct the filenames for the error and output stream
		outfile = self.replace_flags(self.options.ostream, task, jobid)
		errorfile = self.replace_flags(self.options.estream, task, jobid)
		
		real_command = self.replace_flags(self.commandarr, task, jobid)
		
		batchcommand.extend(['-o', outfile, '-e', errorfile])

		#Wrap it in a script file (Escaped)
		script = "#!/bin/bash\n" + "\"" + "\" \"".join(real_command) + "\""
		
		#Call sbatch. Feed in the script through STDIN and catch the result in output
		output = Popen(batchcommand, stdin=PIPE, stdout=PIPE).communicate(script)[0]
		
		#Find the jobid on the end of the line
		m = re.search('[0-9]+$', output)
		self.jobs.append(m.group(0))
		if verbosity > 1:
			print 'Task ' + str(task) + ' is submitted as job ' + m.group(0)
		
	def cancel(self):
		global verbosity
		cancelcommand=['scancel']
		cancelcommand.extend(self.jobs)
		call(cancelcommand)
		if verbosity > 0:
			print 'Jobs are cancelled!'
		sys.exit(255)
		

class LocalRunner(Runner):
	job_id = 0
	num_cores = 1
	
	cancelled = False
	failed = False
	
	processes = []
	mainprocess = None
	
	def __init__(self, options, commandarr):
		super(LocalRunner,self).__init__(options, commandarr)

		
		if options.cores > 0:
			self.num_cores = options.cores
		else:
			self.num_cores = max(1, multiprocessing.cpu_count() + options.cores)
		
		if options.verbosity > 1:
			print str(self.num_cores) + " cores are used"
		
		# Make a job id by counting the number of files in a directory
		# It is lame, but what else makes sense?
		self.job_id = random.randint(1, 9999)
		
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
		
		while q.empty() and not self.cancelled:
			time.sleep(5)
		
		if self.cancelled:
			self.cancel()
		
		allready = False
		while not self.cancelled and not allready:
			allready = True
			for p in self.processes:
				p.join(1)
				if p.is_alive():
					allready = False
			
		if self.cancelled:
			self.cancel()
		
		if(self.failed):
			sys.exit(1)
		
	def runFromQueue(self, q):
		try:
			while not self.cancelled:
				command = q.get_nowait()
				if verbosity > 1:
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
