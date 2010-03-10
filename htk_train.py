#!/usr/bin/python

import job_runner
import htk

scpfile = 'train.scp'
source_hmm_dir = 'hmm02'
target_hmm_dir = 'hmm03'
phones_list = 'monophones0'
transcriptions = 'mono.mlf'
config = 'config'
pruning = ["300.0", "500.0", "2000.0"]

job_runner.default_options["verbosity"] = 5

htk.HERest(scpfile, source_hmm_dir, target_hmm_dir, phones_list, transcriptions, config, pruning)



#job_runner.default_options = {'numtasks': 20}

#job_runner.submit_job(['pwd'], {'verbosity': 2, 'numtasks':22})

print "Finished!"
