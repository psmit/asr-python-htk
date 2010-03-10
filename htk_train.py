#!/usr/bin/python

import job_runner

job_runner.default_options = {'numtasks': 20}

job_runner.submit_job(['HDMan'], {'verbosity': 2})

print "Finished!"
