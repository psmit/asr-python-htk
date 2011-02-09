#!/usr/bin/env python2.6
from optparse import OptionParser
import os
import sys
import time
from htk2.model import HTK_model
from htk2.tools import htk_config
from gridscripts.remote_run import RemoteRunner

start_time = time.time()

usage = "usage: %prog [options] modelname file_list transcription dictionary [model_dir]"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()

if options.config is not None:
    htk_config.load_config_vals(options.config)
htk_config.load_object_vals(options)



if not 4 <= len(args) <= 5:
    parser.print_usage(file=sys.stderr)
    sys.exit(1)

model_dir = None
model_name, scp_list, transcription, dictionary = args[:4]


if len(args) > 4: model_dir = args[5]
if model_dir is None:
    model_dir = os.path.dirname(os.path.abspath(model_name))

model_name = os.path.basename(model_name)

model = HTK_model(model_name, model_dir, htk_config)
model.initialize_new(scp_list,transcription,dictionary,remove_previous=True)

if options.local_allowed and RemoteRunner._select_runner().is_local():
    model.transfer_files_local()

model.flat_start()

for _ in xrange(3): model.re_estimate()

model.introduce_short_pause_model()

for _ in xrange(3): model.re_estimate()
    
model.align_transcription()

for _ in xrange(4): model.re_estimate()

model.transform_to_triphone()

for _ in xrange(2): model.re_estimate()

model.re_estimate(stats=True)

model.tie_triphones()

for _ in xrange(3): model.re_estimate()

for mix in [1, 2, 4, 6, 8, 12, 16]:
    model.split_mixtures(mix)
    for _ in xrange(4): model.re_estimate()


model.clean_files_local()

end_time = time.time()

print end_time - start_time
print "Success"


