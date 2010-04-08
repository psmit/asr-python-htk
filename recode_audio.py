#!/usr/bin/env python2.6
from subprocess import Popen,PIPE
import os
from optparse import OptionParser
from tempfile import mkstemp

usage = "usage: %prog [options] [input-file output-file]"
parser = OptionParser(usage=usage)
parser.add_option("-s", "--set", dest="set", help="Data set (speecon or wsj)", default="")
parser.add_option("-S", "--scp-file", dest="scp", help="SCP file", default=None)
parser.add_option("-a", "--amr", action="store_true", dest="amr", default=False, help="Do amr procedure")
parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity", default=1)
options, files = parser.parse_args()

file_pairs = []
if options.scp is not None:
    for line in open(options.scp):
        input_file, output_file = line.rstrip().split(None, 1)
        file_pairs.append( (input_file, output_file) )

else:
    if len(files) == 2:
        file_pairs.append( (files[0], files[1]) )


for input_file, output_file in file_pairs:
    if options.verbosity > 0:
        print "%s -> %s" % (input_file, output_file)
    ini_command = []
    if options.set == 'wsj':
        ini_command = ['sph2pipe', '-f', 'wav', '-p', input_file]
    else: #speecon
        ini_command = ['sox', '-b', '16', '-e', 'signed-integer', '-r', '16000', '-t', 'raw', input_file, '-t', 'wav', '-']

    if options.amr:
        ini_process = Popen(ini_command, stdout=PIPE)
        fd, iwav_file = mkstemp()
        fd.close()
        fd, amr_file = mkstemp()
        fd.close()
        fd, owav_file = mkstemp()
        fd.close()

        Popen(['sox', '-b', '16', '-e', 'signed-integer', '-r', '16000', '-t', 'wav', ini_process.stdout,
                           '-b', '16', '-e', 'signed-integer', '-r', '8000', '-t', 'raw', iwav_file, 'rate', '-ql']).wait()
        Popen(['amr-encode', 'MR122', iwav_file, amr_file]).wait()
        Popen(['amr-decode', amr_file, owav_file])
        ofile = open(output_file, 'w+b')
        Popen(['sox', '-b', '16', '-e', 'signed-integer', '-r', '8000', '-t', 'raw', owav_file,
                           '-b', '16', '-e', 'signed-integer', '-r', '16000', '-t', 'wav', '-', 'rate', '-ql'], stdout=ofile).wait()
        ofile.close()

        os.remove(iwav_file)
        os.remove(amr_file)
        os.remove(owav_file)
    else:
        ofile = open(output_file, 'w+b')
        Popen(ini_command, stdout=ofile).wait()
        ofile.close()
        


    

