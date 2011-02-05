from multiprocessing.pool import Pool

class _Runner(object):
    def run(self,job):
        pass

class _LocalRunner(_Runner):
    def __init__(self):
        self.pool = None
        
    def run(self,job):
        try:
            job()
        except TypeError:
            try:
                self.pool = Pool()
                results = [self.pool.apply_async(ExceptionWrapper(j)) for j in job]
                self.pool.close()
                self.pool.join()
                self.pool = None
                return [r.get() for r in results]
            
            except KeyboardInterrupt:
                if self.pool is not None:
                    self.pool.terminate()
                    self.pool.join()
                    self.pool = None
                raise

class ExceptionWrapper(object):
    def __init__(self,other_class):
        self.other_class = other_class

    def __call__(self):
        try:
            self.other_class()
        except KeyboardInterrupt:
            pass


class RemoteRunner(object):
    def __init__(self):
        self.runner = RemoteRunner._select_runner()()

    @staticmethod
    def _select_runner():
        return _LocalRunner

    def run(self,job):
        self.runner.run(job)