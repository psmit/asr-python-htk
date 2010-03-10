#!/usr/bin/python

import job_runner
import htk

scpfile = 'train.scp'
config = 'config'

job_runner.default_options["verbosity"] = 5

htk.num_tasks = 500
htk.HCopy(scpfile, config)

print "Finished!"
