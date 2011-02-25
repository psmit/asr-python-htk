#!/usr/bin/env python2.6
import os
import time

print "Start cleaning"

def rmtree(f,min_age):
    t = max(os.stat(f).st_mtime,os.stat(f).st_ctime)

    if os.path.isdir(f):
        for a in os.listdir(f):
            rmtree(os.path.join(f,a),min_age)
        if t + min_age < time.time() and len(os.listdir(f)) is 0:
            os.rmdir(f)
    elif os.path.isfile(f):
        if t + min_age < time.time():
            os.remove(f)


print os.environ


global_delay = 23*60*60
local_delay = 23*60*60
log_delay = (3*24+23)*60*60

if 'LOCAL_TMP' in os.environ and os.path.exists(os.environ['LOCAL_TMP']):
    for d in os.listdir(os.environ['LOCAL_TMP']):
        if d.startswith('tmp'):
            rmtree(os.path.join(os.environ['LOCAL_TMP'],d),local_delay)
            if not os.path.exists(os.path.join(os.environ['LOCAL_TMP'],d)):
                print "{0:>s} deleted".format(os.path.join(os.environ['LOCAL_TMP'], d))

elif 'GLOBAL_TMP' in os.environ:
    for d in os.listdir(os.environ['GLOBAL_TMP']):
        print "check: %s" % d
        if d.startswith('tmp'):
            rmtree(os.path.join(os.environ['GLOBAL_TMP'],d),global_delay)
            if not os.path.exists(os.path.join(os.environ['GLOBAL_TMP'],d)):
                print "{0:>s} deleted".format(os.path.join(os.environ['GLOBAL_TMP'], d))
#        if d.startswith('log'):
#            rmtree(os.path.join(os.environ['GLOBAL_TMP'],d),log_delay)
#            if not os.path.exists(os.path.join(os.environ['GLOBAL_TMP'],d)):
#                print "{0:>s} deleted".format(os.path.join(os.environ['GLOBAL_TMP'], d))

