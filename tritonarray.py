#!/usr/bin/env python2.6

########################################################################
# tritonarray.py
#
# Description:
# ------------
# This script will run an array job in Triton.
# Let's say you want to run the command HCopy on 100 different input files, indexed from 1-100.
# sbatch -N 4 -n 48 -t 00:10:00 --mem-per-cpu=1000 tritonarray.py -o %c.e%j.%t -e %c.e%j.%t -T 1-100 -- HCopy -S inputfile.%t
########################################################################
from subprocess import *
from optparse import OptionParser
import os.path
import time
import sys
import signal

def main():
    parser = getOptParser()
    (options, args) = parser.parse_args()
    
    tarr = TritonArray(options, args)
    tarr.run()
    
class TritonArray(object):
    options = None
    command = None
    jobname = "NoJobName"
    t_start = 1
    t_end = 1
    
    def __init__(self, options, command):
        self.options = options
        self.command = command
        # if a relative script is given, make it more absolute
        if self.command[0][0] != '.' and self.command[0][0] != '/' and os.path.isfile(os.getcwd() + '/' + self.command[0]):
            self.command[0] = os.getcwd() + '/' + self.command[0]
        
        # same with the error and output streams
        if self.options.ostream[0] != '.' and self.options.ostream[0] != '/':
            self.options.ostream = os.getcwd() + '/' + self.options.ostream
        if self.options.estream[0] != '.' and self.options.estream[0] != '/':
            self.options.estream = os.getcwd() + '/' + self.options.estream
            
        # If the outputstreams are just directories, add the default filename pattern
        if os.path.isdir(self.options.ostream):
            self.options.ostream = self.options.ostream + '/%c.o%j.%t'
            
        if os.path.isdir(self.options.estream):
            self.options.estream = self.options.estream + '/%c.e%j.%t'
            
        
        #create a nice job name
        self.jobname = os.path.basename(command[0])
        
        self.parse_task_option()
        
    # Method to detect the task range used
    def parse_task_option(self):
        s, e = self.options.tasks.split('-', 1)
        self.t_start = int(s)
        self.t_end = int(e)
        
        if self.t_start > self.t_end:
            print "Start task is bigger than end task"
            sys.exit(12)
        
    def run(self):
        processes = {}

        cur_t = self.t_start
        num_procs = int(os.getenv('SLURM_NPROCS'))

        all_success = True
        
        while cur_t <= self.t_end or len(processes) > 0:
            for i in range(0,num_procs-len(processes)):
                if cur_t <= self.t_end:
                    srun_command = ['srun']
                    srun_command.extend(['--exclusive'])
                    srun_command.extend(['-t','0'])
                    srun_command.extend(['-J', self.jobname + '.' + str(cur_t)])
                    srun_command.extend(['-n1','-N1'])
                    srun_command.extend(['-o', self.replace_flags(self.options.ostream, cur_t)])
                    srun_command.extend(['-e', self.replace_flags(self.options.estream, cur_t)])
                    srun_command.extend(self.replace_flags(self.command, cur_t))
                    processes[cur_t] = Popen(srun_command)
                    cur_t += 1

            for task in processes.keys():
                if processes[task].poll() is not None:
                    if processes[task].returncode != 0:
                        if self.options.printfail:
                            print "Error: task " + str(task) + " failed with code " + str(returncode)
                        all_success = False
                    else:
                        print "Task %s succeeded" % task
                    del processes[task]

            time.sleep(2)
        
        # Give a failure exit code when not all tasks succeeded.
        if not all_success:
            sys.exit(20)
    
    def replace_flags(self, pattern, task):
        ret = pattern
        
        if type(ret).__name__=='list':
            ret = [str(item).replace('%t', str(task)) for item in ret]
        else:
            ret = ret.replace('%c', self.jobname)
            ret = ret.replace('%t', str(task))
            ret = ret.replace('%J', os.getenv("SLURM_JOBID"))
        return ret
            
def getOptParser():
    usage = "usage: %prog [options] -- command"
    parser = OptionParser(usage=usage)
    parser.add_option("-T", "--tasks", dest="tasks", help="Task definition. Standard format: n-m (e.g. 1-100)", default="1-1")
    parser.add_option("-o", "--output-stream", dest="ostream", help="write outputstream to FILE (%c for command, %J for job id, %t for task id). If a directory is given, the default format is used in that directory", default="%c.o%j.%t", metavar="FILE")
    parser.add_option("-e", "--error-stream", dest="estream", help="write outputstream to FILE (%c for command, %J for job id, %t for task id). If a directory is given, the default format is used in that directory", default="%c.e%j.%t", metavar="FILE")
    parser.add_option("-f", "--print-failure", action="store_true", dest="printfail", help="Print the exit codes for failed tasks", default=False)
    return parser

def signal_handler(signal, frame):

    print 'Signal %s received!' % signal
    sys.exit(255)

#Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    main()
