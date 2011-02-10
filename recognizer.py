from __future__ import print_function

import os
import shutil
from htk2.tools import HDecode, HERest, HHEd, HVite
from gridscripts.remote_run import System
from htk2.units import HTK_transcription, HTK_dictionary

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

        self.language_model = language_model

        self.htk_config = htk_config

        self.adaptations = []

        self.id = 0
        System.set_log_dir(os.path.basename(name))


    def add_adaptation(self,scp_file,mlf_file,num_speaker_chars=None,files_per_speaker=None):
        tmp_dir = System.get_global_temp_dir()
        phone_mlf = os.path.join(tmp_dir,'phone.mlf')

        new_extension = 'mllr{0:d}'.format(len(self.adaptations) - 1)

        HVite(self.htk_config,scp_file,self.model+'.mmf',self.dict,self.model+'.hmmlist',phone_mlf,mlf_file).run()

        in_transform = None
        if len(self.adaptations) > 0:
            in_transform = [self.adaptations[-1],(self.classes_dir,None)]

        HERest(self.htk_config,scp_file,self.model+'.mmf',self.model+'.hmmlist',phone_mlf,num_speaker_chars=num_speaker_chars,
               max_adap_sentences=files_per_speaker,input_adaptation=in_transform,parent_adaptation=in_transform,output_adaptation=[(self.xforms_dir,new_extension)]).run()

        self.adaptations.append((self.xforms_dir,new_extension))

        shutil.rmtree(tmp_dir)


    def recognize(self,lm_scale,sub_name = None):
        tmp_dir = System.get_global_temp_dir()

        in_transform = None
        if len(self.adaptations) > 0:
            in_transform = [self.adaptations[-1],(self.classes_dir,None)]

        if sub_name is None:
            sub_name = str(self.id)

        HDecode(self.htk_config,self.scp,self.model+'.mmf',self.dict,self.model+'.hmmlist',self.language_model,self.name+'.'+sub_name+'.mlf',lm_scale=lm_scale,adapt_dirs=in_transform).run()

#        trans = HTK_transcription()
#        trans.read_mlf(self.name+'.'+sub_name+'.mlf',target=HTK_transcription.WORD)
#        trans.write_trn(self.name+'.'+sub_name+'.trn')

        shutil.rmtree(tmp_dir)