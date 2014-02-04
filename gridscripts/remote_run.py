import collections
import os
import sys
import time

from multiprocessing.pool import Pool, cpu_count
from subprocess import Popen
from tempfile import mkdtemp


class JobFailedException(Exception): pass

class System(object):
    log_dir = None

    @staticmethod
    def get_global_temp_dir():
        try:
            return mkdtemp(dir=os.environ['GLOBAL_TMP'])
        except KeyError:
            sys.exit("Please set the GLOBAL_TMP environment variable to a directory for temporary files")

    @staticmethod
    def get_local_temp_dir():
        try:
            if not os.path.exists(os.environ['LOCAL_TMP']):
                os.mkdir(os.environ['LOCAL_TMP'], 0700)
            return mkdtemp(dir=os.environ['LOCAL_TMP'])
        except KeyError:
            sys.exit("Please set the LOCAL_TMP environment variable to a directory for temporary files")
        except OSError:
            sys.exit("The LOCAL_TMP directory does not seem to exist")

    @classmethod
    def set_log_dir(cls,name):
        if not os.path.exists(os.path.join(os.environ['GLOBAL_TMP'],'log')):
            os.mkdir(os.path.join(os.environ['GLOBAL_TMP'],'log'))

        cls.log_dir = os.path.join(os.environ['GLOBAL_TMP'],'log',name)
        if not os.path.exists(cls.log_dir):
            os.mkdir(cls.log_dir)

    @classmethod
    def get_log_dir(cls):
        if cls.log_dir is None:
            sys.exit("Please set log dir")
        return cls.log_dir

class RemoteRunner(object):
    _runner = None

    def __init__(self,job):
        self.job = job

    @classmethod
    def _select_runner(cls):
        if cls._runner is None:
            cls._runner = _LocalRunner

        return cls._runner


    def __call__(self):
        RemoteRunner._select_runner()().run(self.job)

        
class Job(object):
    max_num_retries = 2
    cleaning = True
    name = 'NoName'
    format = '{time}.{name}.'
    stdout = sys.stdout
    stderr = sys.stderr

    def _run(self):     raise NotImplementedError
    def __call__(self): raise NotImplementedError
    def get_name(self): return self.__class__.__name__
    def test_success(self): return True
    def _clean(self,keep_input_files=False): pass
    def prepare_retry(self): self._clean(True)


    def run(self):
        RemoteRunner(self)()

class AtomicJob(Job):
    def __call__(self):
        self._run()

class SplittableJob(Job):
    max_num_tasks = 10

    def __init__(self):
        self.max_num_tasks = RemoteRunner._select_runner().max_tasks()
        self.tasks = []

    def _split_to_tasks(self):
        pass

    def _merge_tasks(self):
        pass

class CollectionJob(SplittableJob):

    def __init__(self,jobs):
        super(CollectionJob,self).__init__()
        self.job_collection = list(jobs)

    def _split_to_tasks(self):
        for j in self.job_collection:
            if isinstance(j, SplittableJob):
                j._split_to_tasks()
                self.tasks.extend(j.tasks)
            else:
                self.tasks.append(j)

    def _merge_tasks(self):
        for j in self.job_collection:
            if isinstance(j, SplittableJob):
                j._merge_tasks()

#    def __call__(self):
#        self._split_to_tasks()
#
#        RemoteRunner().run(self.tasks)
#
#        self._merge_tasks()


class Task(AtomicJob):
    max_task_retries = 3

    def __init__(self, task_id=0):
        self.task_id = task_id

    def get_name(self):
        return "{0:>s}.{1:03d}".format(self.__class__.__name__, self.task_id)


class BashJob(AtomicJob):
    def __init__(self):
        self.command = []

    def _run(self):
        p = Popen(self.command, stdout=self.stdout, stderr=self.stderr)
        p.wait()
        if p.returncode is not 0:
            raise JobFailedException

class _Runner(object):
    def __init__(self, max_tries = 3):
        self.max_tries = max_tries

    @classmethod
    def is_local(cls):
        return False

    def run(self,job):
        pass

class _LocalRunner(_Runner):
    def __init__(self, max_tries = 3):
        super(_LocalRunner,self).__init__(max_tries)
        self.pool = None

    @classmethod
    def is_local(cls):
        return True
    
    @classmethod
    def max_tasks(cls):
        return cpu_count()
    
    def run(self,job):
        if isinstance(job, SplittableJob):
            job._split_to_tasks()
            jobs = job.tasks

        elif isinstance(job, collections.Callable):
            jobs = [job]

        else:
            jobs = job
            

#        for i,j in enumerate(jobs):
#            jw = JobWrapper(j)
#            jw()
            
        try:
            self.pool = Pool()
            results = [self.pool.apply_async(JobWrapper(j)) for j in jobs]

            for try_n in xrange(self.max_tries):

                for i, result in enumerate(results):
                    if result is not None:
                        result.wait()
                        if result.successful() and jobs[i].test_success():
                            results[i] = None
                        else:
                            try:
                                jobs[i].prepare_retry()
                            except TypeError:
                                pass

                            results[i] = self.pool.apply_async(JobWrapper(jobs[i]))

                    #Stop loop if all results were OK
                    if all(r is None for r in results):
                        break

            self.pool.close()
            self.pool.join()
            self.pool = None

            if not all(r is None for r in results):
                raise JobFailedException

        except (KeyboardInterrupt, SystemExit):
            if self.pool is not None:
                self.pool.terminate()
                self.pool.join()
                self.pool = None
            raise

        if isinstance(job, SplittableJob):
            job._merge_tasks()

class JobWrapper(object):
    def __init__(self,wrapped_object,try_num=0):
        self.wrapped_object = wrapped_object
        self.try_num = try_num
        self.log_dir = System.get_log_dir()


    def __call__(self):
        self.wrapped_object.stdout = open(os.path.join(self.log_dir, "{0:d}.{1:>s}.o.{2:d}".format(int(time.time()), self.wrapped_object.get_name(),self.try_num)), 'w')
        self.wrapped_object.stderr = open(os.path.join(self.log_dir, "{0:d}.{1:>s}.e.{2:d}".format(int(time.time()), self.wrapped_object.get_name(),self.try_num)), 'w')
        
        try:
            self.wrapped_object()
        except KeyboardInterrupt:
            pass
        finally:
            self.wrapped_object.stdout.close()
            self.wrapped_object.stderr.close()


