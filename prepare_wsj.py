#!/usr/bin/python

import job_runner
import htk

scpfile = 'combined_train.scp'
config = 'config.hcopy'

job_runner.default_options["verbosity"] = 5
job_runner.default_options["memlimit"] = 1000
job_runner.default_options["timelimit"] = "01:00:00"

htk.num_tasks = 100
htk.HCopy(scpfile, config)

print "Finished!"
