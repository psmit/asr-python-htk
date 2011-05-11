from __future__ import print_function
import glob
from itertools import izip

import os
from random import shuffle
from os.path import basename
import shutil
from htk2.tools import HDecode, HERest, HHEd, HVite
from gridscripts.remote_run import System
from htk2.units import HTK_transcription, HTK_dictionary
import htk_file_strings
from gridscripts.remote_run import CollectionJob

class HTK_recognizer(object):
    def __init__(self, htk_config, name, model, scp, dictionary, language_model):
        if not name.startswith('/'):
            name = os.path.join(os.getcwd(), name)

        if htk_config.num_speaker_chars < 0:
            htk_config.num_speaker_chars = 3
            
        self.name = name
        if os.path.exists(name):
            shutil.rmtree(name,ignore_errors=True)
        os.mkdir(name)

        self.a_id = 0
        self.xforms_dir = os.path.join(name,'xforms%d'%self.a_id)
        os.mkdir(self.xforms_dir)

        self.classes_dir = os.path.join(name,'classes%d'%self.a_id)
        os.mkdir(self.classes_dir)

        self.model = model

        self.split_scp_models = []


        if '?' in scp:
            self.scp = None
            num_scp_speaker_chars = 1
            while '?' * (num_scp_speaker_chars + 1) in scp:
                num_scp_speaker_chars += 1
            s_index = scp.find('?' * num_scp_speaker_chars)

            speakers = [s[s_index:s_index+num_scp_speaker_chars] for s in glob.iglob(scp)]

            for s in speakers:
                real_scp = os.path.join(name,'%s_list.scp'%s)
                with open(real_scp, 'w') as scp_desc:
                    for line in open(scp.replace('?' * num_scp_speaker_chars, s)):
                        print(os.path.join(os.path.dirname(scp), line.strip()),file=scp_desc)
                self.split_scp_models.append(
                    (s,real_scp,model.replace('?' * num_scp_speaker_chars, s))
                )
        else:
            self.scp = os.path.join(name,'list.scp')
            with open(self.scp, 'w') as scp_desc:
                for line in open(scp):
                    print(os.path.join(os.path.dirname(scp), line.strip()),file=scp_desc)

        self.dict = dictionary

        d = HTK_dictionary()
        d.read_dict(dictionary)

        self.dict = os.path.join(name, 'dict.hdecode')
        d.write_dict(self.dict,False)

        d = HTK_dictionary()
        d.read_dict(htk_config.adap_align_dict)
        self.adap_align_dict = os.path.join(name, 'dict.hvite')
        d.write_dict(self.adap_align_dict,True)


        self.language_model = language_model

        self.htk_config = htk_config

        self.adaptations = []
        self.adap_num_speaker_chars = None

        self.id = 0
        System.set_log_dir(os.path.basename(name))

        
    def clear_adaptations(self):
        self.adaptations = []
        self.adap_num_speaker_chars = None

        self.a_id += 1
        self.xforms_dir = os.path.join(self.name,'xforms%d'%self.a_id)
        os.mkdir(self.xforms_dir)

        self.classes_dir = os.path.join(self.name,'classes%d'%self.a_id)
        os.mkdir(self.classes_dir)

    def add_adaptation(self,scp_file,mlf_file,num_nodes = 1,num_speaker_chars=None,files_per_speaker=None,split_threshold=1000):

        new_extension = 'mllr{0:d}'.format(len(self.adaptations))

        tmp_dirs = []
        hvite_tasks = []
        hed_tasks = []
        herest_tasks = []

        real_scp_files = [scp_file]
        speakers = [""]
        models = [self.model]


        if self.scp is None:
            l = len(self.split_scp_models[0][0])
            real_scp_files = [scp_file.replace('?'*l, sp[0]) for sp in self.split_scp_models]
            speakers = [sp[0] for sp in self.split_scp_models]
            models = [sp[2] for sp in self.split_scp_models]

        for scp_file, speaker, model in izip(real_scp_files,speakers,models):
            tmp_dir = System.get_global_temp_dir()
            tmp_dirs.append(tmp_dir)

            phone_mlf = os.path.join(tmp_dir,'phone.mlf')

            tmp_scp_file = os.path.join(tmp_dir,'adap.scp')
            with open(tmp_scp_file,'w') as tmp_desc:
                smap = {}
                for line in open(scp_file):
                    if basename(line)[:num_speaker_chars] not in smap:
                        smap[basename(line)[:num_speaker_chars]] = []
                    smap[basename(line)[:num_speaker_chars]].append(line.strip())

                for sp,f in smap.iteritems():
                    shuffle(f)
                    for line in f:

                    #for line in open(scp_file):
                        if not line.startswith('/'):
                            print(os.path.join(os.path.dirname(scp_file), line.strip()),file=tmp_desc)
                        else:
                            print(line.strip(),file=tmp_desc)

            tmp_config = os.path.join(tmp_dir,'hvite_config')
            with open(tmp_config,'w') as tmp_desc:
                print(htk_file_strings.HVITE_CONFIG, file=tmp_desc)

            hvite_tasks.append(HVite(self.htk_config,tmp_scp_file,model+'.mmf',self.adap_align_dict,model+'.hmmlist',phone_mlf,mlf_file,config_file=tmp_config))

            in_transform = []
            parent_transform = None
            if len(self.adaptations) > 0:
                in_transform = [self.adaptations[-1]]
            in_transform.append((self.classes_dir,None))

            if len(in_transform) > 1:
                parent_transform = in_transform

            adap_config = os.path.join(tmp_dir, 'adap_config')
            if num_nodes == 1: # global adaptation
                global_name = 'global{0:d}'.format(len(self.adaptations))
                global_file = os.path.join(self.classes_dir,global_name)
                with open(global_file, 'w') as global_desc:
                    print(htk_file_strings.GLOBAL.format(global_name=global_name),file=global_desc)
                with open(adap_config, 'w') as adap_desc:
                    print(htk_file_strings.BASE_ADAP_CONFIG.format(base_class=global_name),file=adap_desc)
                    if self.adap_num_speaker_chars is not None:
                        mask = "*/" + ('%' * self.adap_num_speaker_chars) + "*.*"
                        print("PAXFORMMASK = {mask:>s}\nINXFORMMASK = {mask:>s}".format(mask=mask),file=adap_desc)



            else: # tree adaptation
                regtree_name = '{0:>s}regtree{1:d}'.format(speaker,len(self.adaptations))
                regtree_hed = os.path.join(tmp_dir,'regtree.hed')
                with open(regtree_hed,'w') as regtree_desc:
                    print(htk_file_strings.REGTREE_HED.format(stats_file=model+'.stats',num_nodes=num_nodes,regtree=regtree_name),file=regtree_desc)
                hed_tasks.append(HHEd(self.htk_config,model+'.mmf',self.classes_dir,model+'.hmmlist',regtree_hed))
                with open(adap_config, 'w') as adap_desc:
                    print(htk_file_strings.TREE_ADAP_CONFIG.format(regtree=os.path.join(self.classes_dir,regtree_name)+'.tree'),file=adap_desc)
                    if self.adap_num_speaker_chars is not None:
                        mask = "*/" + ('%' * self.adap_num_speaker_chars) + "*.*"
                        print("PAXFORMMASK = {mask:>s}\nINXFORMMASK = {mask:>s}".format(mask=mask),file=adap_desc)
                    if self.htk_config.split_threshold is not 1000:
                        print("HADAPT:SPLITTHRESH = {0:.1f}".format(float(self.htk_config.split_threshold)), file=adap_desc)


            herest_tasks.append(HERest(self.htk_config,tmp_scp_file,model+'.mmf',model+'.hmmlist',phone_mlf,config_file=adap_config,
                   num_speaker_chars=num_speaker_chars, max_adap_sentences=files_per_speaker,
                   input_adaptation=in_transform,parent_adaptation=parent_transform,output_adaptation=(self.xforms_dir,new_extension)))


        if len(hvite_tasks) == 1:
            hvite_tasks[0].run()
        elif len(hvite_tasks) > 1:
            CollectionJob(hvite_tasks).run()

        if len(hed_tasks) == 1:
            hed_tasks[0].run()
        elif len(hed_tasks) > 1:
            CollectionJob(hed_tasks).run()

        if len(herest_tasks) == 1:
            herest_tasks[0].run()
        elif len(herest_tasks) > 1:
            CollectionJob(herest_tasks).run()

        self.adaptations.append((self.xforms_dir,new_extension))

        self.adap_num_speaker_chars = num_speaker_chars
        
        [shutil.rmtree(tmp_dir,ignore_errors=True) for tmp_dir in tmp_dirs]


    def recognize(self,lm_scale,sub_name = None):
        tmp_dir = System.get_global_temp_dir()

        in_transform = None
        if len(self.adaptations) > 0:
            in_transform = [self.adaptations[-1],(self.classes_dir,None)]

        if sub_name is None:
            sub_name = str(self.id)

        if self.scp is None:
            t = []
            for speaker,scp,model in self.split_scp_models:
                t.append(HDecode(self.htk_config,scp,model+'.mmf',self.dict,model+'.hmmlist',self.language_model,self.name+'.'+sub_name+'.'+speaker+'.mlf',lm_scale=lm_scale,adapt_dirs=in_transform,adapt_speaker_chars=self.adap_num_speaker_chars))
            CollectionJob(t).run()
            HTK_recognizer._combine_output_files(self.name+'.'+sub_name+'.*.mlf',self.name+'.'+sub_name+'.mlf')
        else:
            HDecode(self.htk_config,self.scp,self.model+'.mmf',self.dict,self.model+'.hmmlist',self.language_model,self.name+'.'+sub_name+'.mlf',lm_scale=lm_scale,adapt_dirs=in_transform,adapt_speaker_chars=self.adap_num_speaker_chars).run()

#        trans = HTK_transcription()
#        trans.read_mlf(self.name+'.'+sub_name+'.mlf',target=HTK_transcription.WORD)
#        trans.write_trn(self.name+'.'+sub_name+'.trn')

        shutil.rmtree(tmp_dir,ignore_errors=True)

    @staticmethod
    def _combine_output_files(input_files, output_file):
        for ext in ['mlf','trn']:
            with open(output_file[:-3] + ext,'w') as out_desc:
                for ifile in glob.iglob(input_files[:-3]+ext):
                    for line in open(ifile):
                        print(line.strip(), file=out_desc)
                    os.remove(ifile)
            
