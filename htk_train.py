#!/usr/bin/python

import job_runner

job_runner.default_options = {'numtasks': 20}

job_runner.submit_job(['pwd'], {'verbosity': 2, 'numtasks':22})

print "Finished!"
