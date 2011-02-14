from __future__ import print_function

import os
import shutil
from htk2.tools import HDecode, HERest, HHEd, HVite
from gridscripts.remote_run import System
from htk2.units import HTK_transcription, HTK_dictionary
import htk_file_strings

class HTK_recognizer(object):
    def __init__(self, htk_config, name, model, scp, dictionary, language_model):
        if not name.startswith('/'):
            name = os.path.join(os.getcwd(), name)

        if htk_config.num_speaker_chars < 0:
            htk_config.num_speaker_chars = 3
            
        self.name = name
        if os.path.exists(name):
            shutil.rmtree(name)
        os.mkdir(name)

        self.xforms_dir = os.path.join(name,'xforms')
        os.mkdir(self.xforms_dir)

        self.classes_dir = os.path.join(name,'classes')
        os.mkdir(self.classes_dir)


        self.model = model

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


    def add_adaptation(self,scp_file,mlf_file,num_nodes = 1,num_speaker_chars=None,files_per_speaker=None):
        tmp_dir = System.get_global_temp_dir()
        phone_mlf = os.path.join(tmp_dir,'phone.mlf')

        tmp_scp_file = os.path.join(tmp_dir,'adap.scp')
        with open(tmp_scp_file,'w') as tmp_desc:
            for line in open(scp_file):
                if not line.startswith('/'):
                    print(os.path.join(os.path.dirname(scp_file), line.strip()),file=tmp_desc)



        new_extension = 'mllr{0:d}'.format(len(self.adaptations))

        tmp_config = os.path.join(tmp_dir,'hvite_config')
        with open(tmp_config,'w') as tmp_desc:
            print(htk_file_strings.HVITE_CONFIG, file=tmp_desc)

        HVite(self.htk_config,tmp_scp_file,self.model+'.mmf',self.adap_align_dict,self.model+'.hmmlist',phone_mlf,mlf_file,config_file=tmp_config).run()

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
                    print("PAXFORMMASK = *.{mask:>s}\nINXFORMMASK = *.{mask:>s}".format(mask=mask),file=adap_desc)



        else: # tree adaptation
            regtree_name = 'regtree{0:d}'.format(len(self.adaptations))
            regtree_hed = os.path.join(tmp_dir,'regtree.hed')
            with open(regtree_hed,'w') as regtree_desc:
                print(htk_file_strings.REGTREE_HED.format(stats_file=self.model+'.stats',num_nodes=num_nodes,regtree=regtree_name),file=regtree_desc)
            HHEd(self.htk_config,self.model+'.mmf',self.classes_dir,self.model+'.hmmlist',regtree_hed).run()
            with open(adap_config, 'w') as adap_desc:
                print(htk_file_strings.TREE_ADAP_CONFIG.format(regtree=os.path.join(self.classes_dir,regtree_name)+'.tree'),file=adap_desc)
                if self.adap_num_speaker_chars is not None:
                    mask = "*/" + ('%' * self.adap_num_speaker_chars) + "*.*"
                    print("PAXFORMMASK = *.{mask:>s}\nINXFORMMASK = *.{mask:>s}".format(mask=mask),file=adap_desc)
                    

        HERest(self.htk_config,tmp_scp_file,self.model+'.mmf',self.model+'.hmmlist',phone_mlf,config_file=adap_config,
               num_speaker_chars=num_speaker_chars, max_adap_sentences=files_per_speaker,
               input_adaptation=in_transform,parent_adaptation=parent_transform,output_adaptation=(self.xforms_dir,new_extension)).run()

        self.adaptations.append((self.xforms_dir,new_extension))

        self.adap_num_speaker_chars = num_speaker_chars
        
        shutil.rmtree(tmp_dir)


    def recognize(self,lm_scale,sub_name = None):
        tmp_dir = System.get_global_temp_dir()

        in_transform = None
        if len(self.adaptations) > 0:
            in_transform = [self.adaptations[-1],(self.classes_dir,None)]

        if sub_name is None:
            sub_name = str(self.id)

        HDecode(self.htk_config,self.scp,self.model+'.mmf',self.dict,self.model+'.hmmlist',self.language_model,self.name+'.'+sub_name+'.mlf',lm_scale=lm_scale,adapt_dirs=in_transform,adapt_speaker_chars=self.adap_num_speaker_chars).run()

#        trans = HTK_transcription()
#        trans.read_mlf(self.name+'.'+sub_name+'.mlf',target=HTK_transcription.WORD)
#        trans.write_trn(self.name+'.'+sub_name+'.trn')

        shutil.rmtree(tmp_dir)