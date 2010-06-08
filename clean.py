#!/usr/bin/env python2.6
# -*- coding: utf-8 -*-


from optparse import OptionParser, os
from glob import glob
import shutil


usage = "usage: %prog [options] [directories]"
parser = OptionParser(usage=usage)
parser.add_option("-l", "--level", type="int", dest="level",help="Level of cleaning. 1: lattices, 2: log files, 3: adaptation matrices", default=1)

options, dirs = parser.parse_args()

if len(dirs) == 0:
    dirs = ['.']


for dir in dirs:
    for directory in glob.iglob(dir):
        if options.level > 0:
            print "Cleaning lattices from %s" % directory

            for latdir in glob.iglob(directory + '/*/lattices.*'):
                shutil.rmtree(latdir)

        if options.level > 1:
            print "Cleaning individual log files from %s" % directory

            if os.path.exists(directory + '/log/tasks'):
                shutil.rmtree(directory + '/log/tasks')

        if options.level > 1:
            print "Cleaning adaptation matrices from %s" % directory

            for xformdir in glob.iglob(directory + '/*/xforms'):
                shutil.rmtree(xformdir)


