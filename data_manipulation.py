#!/usr/bin/python
from __future__ import with_statement

import glob
import os
import os.path
import re
import shutil
import sys



def import_dictionaries(dicts):
	if os.path.isdir('dictionary'): shutil.rmtree('dictionary')
	os.mkdir('dictionary')
	dict = {}
	for location, prefix in dicts:
		if not os.path.exists(location + '/dict'):
			sys.exit("Not Found: " + location + '/dict')
		for line in open(location + '/dict'):
			word, transcription = line.split(None, 1)
			dict[unescape(word.lower())] = [prefix + phone.lower() for phone in transcription.split()]
	
		with open('dictionary/dict', 'w') as dictfile:
			for key in sorted(dict):
				print >> dictfile, "%s %s" % (escape(key), ' '.join(dict[key]))

def unescape(word):
	if re.match("^\\\\[^a-z0-9<]", word): return word[1:]
	else: return word

def escape(word):
	if re.match("^[^a-z0-9<]", word): return "\\" + word
	else: return word
	
def import_corpora(corpora):
	if os.path.isdir('corpora'): shutil.rmtree('corpora')
	os.mkdir('corpora')
	sets = ['train', 'eval', 'devel']
	
	locationmap = {}
	count = 0
	for location, prefix in corpora:
		if not os.path.exists(location + '/mfc'): sys.exit("Not Found: " + location + '/mfc')
		locationmap[location] = location + '/mfc'
		if os.path.islink(location + '/mfc'):
			count += 1
			os.symlink(os.path.join(os.path.dirname(location + '/mfc'), os.readlink(location + '/mfc')), 'corpora/mfc' + str(count))
			locationmap[location] = 'corpora/mfc' + str(count)
		
	for set in sets:
		with open('corpora/'+set+'.scp', 'w') as scpfile:
			for location, prefix in corpora:
				if not os.path.exists(location + '/'+set+'.scp'): sys.exit("Not Found: " + location + '/'+set+'.scp')
				for line in  open(location + '/'+set+'.scp'):
					print >> scpfile, locationmap[location] + line[line.find('/'):].rstrip()
	
	with open('corpora/words.mlf', 'w') as mlffile:
		for location, prefix in corpora:
			if not os.path.exists(location + '/words.mlf'): sys.exit("Not Found: " + location + '/words.mlf')
			for line in open(location + '/words.mlf'):
				if line[0] == '#' or line[0] == '"' or line[0] == '.':
					print >> mlffile, line.rstrip()
				else:
					print >> mlffile, prefix + line.rstrip()
