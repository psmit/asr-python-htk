from __future__ import print_function
import glob
import os
import shutil
from tools import *
from units import HTK_dictionary,HTK_transcription


__author__ = 'peter'

class ExistingFilesException(Exception): pass

#class TrainLogger(object):
#    a = []
#    def __init__(self,f):
#        self.f = f
#        self.__name__ = f.__name__
#
#    def __call__(self,*args,**kwargs):
#        print("Calling %s" % self.__name__)
#        self.a.append(self.__name__)
#        self.f(self, *args,**kwargs)


class HTK_model(object):
    def __init__(self, name, model_dir, htk_config):
        self.name = name

        self.model_dir = model_dir
        self.train_files_dir = os.path.join(self.model_dir, self.name)

        self.training_scp = os.path.join(self.train_files_dir, 'train.scp')
        self.training_word_mlf = os.path.join(self.train_files_dir, 'word.mlf')
        self.training_phone_mlf = os.path.join(self.train_files_dir, 'phone.mlf')
        self.training_dict = os.path.join(self.train_files_dir,'dict')

        self.htk_config = htk_config
        self.training_files_speaker_name_chars = 3

        self.phones = []
        self.id = None


    def get_model_name_id(self,prev=0):
        id = self.id-prev
        return self.model_dir + '/' + "{0}.{1:02d}".format(self.name,id)
    

    def initialize_new(self, scp_list, word_mlf, dict, remove_previous=False):
        System.set_log_dir(self.name)
        if remove_previous:
            for f in glob.iglob(System.get_log_dir()+'/*'): os.remove(f)

        if not remove_previous and (os.path.exists(self.train_files_dir) or len(glob.glob(self.model_dir + '/' + self.name + '.*')) > 0):
            raise ExistingFilesException

        if os.path.exists(self.train_files_dir): shutil.rmtree(self.train_files_dir)
        for f in glob.iglob(self.model_dir + '/' + self.name + '.*'): os.remove(f)
        os.mkdir(self.train_files_dir)

        # handle dictionary
        dic = HTK_dictionary()
        if isinstance(dict,basestring):
            dic.read_dict(dict)
        elif all(isinstance(d,basestring) for d in dict):
            for d in dict:
                dic.read_dict(d)
        else:
            raise TypeError
        dic.write_dict(self.training_dict)

        self.phones = dic.get_phones()


        # handle transcription
        trans = HTK_transcription()
        if isinstance(word_mlf,basestring):
            trans.read_mlf(word_mlf, HTK_transcription.WORD)
        elif all(isinstance(w,basestring) for w in word_mlf):
            for w in word_mlf:
                trans.read_mlf(w, HTK_transcription.WORD)
        else:
            raise TypeError


        self.id = 1

        phones_list = self.get_model_name_id() + '.hmmlist'
        with open(phones_list, 'w') as phones_desc:
            for p in self.phones:
                print(p, file=phones_desc)


        # handle scp files
        if isinstance(scp_list,basestring):
            scp_list = [scp_list]

        real_trans = HTK_transcription()
        real_trans.transcriptions[real_trans.WORD] = {}

        with open(self.training_scp, 'w') as scp_desc:
            for scp in scp_list:
                for file in open(scp):
                    id = os.path.splitext(os.path.basename(file.strip()))[0]

                    ok = True

                    for word in trans.transcriptions[HTK_transcription.WORD][id]:
                        if word not in dic.dictionary:
                            print("%s skipped, because has missing word %s" % (file.strip(), word))
                            ok = False
                            break        
                    if ok:
                        print(file.strip(),file=scp_desc)
                        real_trans.transcriptions[real_trans.WORD][id] = trans.transcriptions[real_trans.WORD][id]

        real_trans.write_mlf(self.training_word_mlf,target=HTK_transcription.WORD)
        self.expand_word_transcription()

    def initialize_existing(self):
        pass

    def expand_word_transcription(self, use_sp=False):
        tmp_dir = System.get_global_temp_dir()
        mkmono = os.path.join(tmp_dir,'mkmono.led')

        with open(mkmono, 'w') as mkmono_desc:
            print("""EX
IS sil sil""" ,file=mkmono_desc)
        
            if use_sp:
                self.training_phone_mlf = os.path.join(self.train_files_dir, 'phone1.mlf')
            else:
                self.training_phone_mlf = os.path.join(self.train_files_dir, 'phone0.mlf')
                print("DE sp", file=mkmono_desc)

        HLEd(self.htk_config, self.training_word_mlf, mkmono, self.get_model_name_id() + '.hmmlist', self.training_dict,self.training_phone_mlf).run()


        shutil.rmtree(tmp_dir)

    def align_transcription(self):
        self.training_phone_mlf = os.path.join(self.train_files_dir, 'phone_aligned.mlf')

#        htk.HVite(current_step, scpfile, target_hmm_dir, dict, phones_list, 'files/words.mlf', transcriptions)
        HVite(self.htk_config, self.training_scp, self.get_model_name_id() + '.mmf', self.training_dict, self.get_model_name_id() + '.hmmlist', self.training_phone_mlf, self.training_word_mlf).run()

    def flat_start(self):
        tmp_dir = System.get_global_temp_dir()
        proto_file = os.path.join(tmp_dir, 'proto')
        vFloors = os.path.join(tmp_dir, 'vFloors')

        with open(proto_file, 'w') as proto_desc:
            print("""~o <VecSize> 39 <MFCC_0_D_A_Z>
~h "proto"
<BeginHMM>
        <NumStates> 5
        <State> 2
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
        <State> 3
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
        <State> 4
                <Mean> 39
0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0 0.0
                <Variance> 39
                1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0 1.0
<TransP> 5
0.0 1.0 0.0 0.0 0.0
0.0 0.6 0.4 0.0 0.0
0.0 0.0 0.6 0.4 0.0
0.0 0.0 0.0 0.7 0.3
0.0 0.0 0.0 0.0 0.0
<EndHMM>""", file=proto_desc)

#        runner = RemoteRunner()
#        runner.run(HCompV(self.htk_config, self.training_scp, proto_file))
        HCompV(self.htk_config, self.training_scp, proto_file).run()


        out_model = self.get_model_name_id() + ".mmf"

        model_def = ""
        phone_def = ""
        in_model_def = True

        for line in open(proto_file):
            if line[0:2] == '~h': in_model_def = False
            if in_model_def: model_def += line
            else: phone_def += line

        #Write model file
        with open(out_model, 'w') as model_desc:
            print(model_def, file=model_desc)
            for line in open(vFloors):
                print(line.strip(), file=model_desc)

            #Write the hmmdefs  (replacing for each monophone, proto with the monophone)
            for line in open( self.get_model_name_id() + '.hmmlist'):
                print(phone_def.replace('proto', line.rstrip()), file=model_desc)
                
        shutil.rmtree(tmp_dir)
        
    def re_estimate(self):
        self.id += 1
        shutil.copyfile(self.get_model_name_id(1)+'.hmmlist',self.get_model_name_id()+'.hmmlist')
        HERest(self.htk_config, self.training_scp,self.get_model_name_id(1)+'.mmf',self.get_model_name_id()+'.hmmlist',
               self.training_phone_mlf,output_hmm_model=self.get_model_name_id()+'.mmf').run()


    def introduce_short_pause_model(self):
        self.id += 1
        phones = [p.strip() for p in open(self.get_model_name_id(1)+'.hmmlist')]
        phones.append('sp')

        with open(self.get_model_name_id()+'.hmmlist', 'w') as phone_out:
            for p in sorted(set(phones)):
                print(p,file=phone_out)

        #copy sil state 3 to sp
        in_sil = False
        in_state3 = False

        state = ""

        with open(self.get_model_name_id()+'.mmf', 'w') as model_desc:
            for line in open(self.get_model_name_id(1)+'.mmf'):
                print(line, file=model_desc)

                if line.startswith('~h'):
                    if line.startswith('~h "sil"'): in_sil = True
                    else: in_sil = False
                elif line.startswith('<STATE>'):
                    if line.startswith('<STATE> 3'): in_state3 = True
                    else: in_state3 = False
                elif in_sil and in_state3:
                    state += line

            print(  "~h \"sp\" <BEGINHMM> <NUMSTATES> 3", file=model_desc)
            print( "<STATE> 2", file=model_desc)
            print(  state, file=model_desc)
            print( """<TRANSP> 3
             0.000000e+00 5.000000e-01 5.000000e-01
             0.000000e+00 5.000000e-01 5.000000e-01
             0.000000e+00 0.000000e+00 0.000000e+00
            <ENDHMM>""", file=model_desc)

        self.id += 1
        shutil.copyfile(self.get_model_name_id(1)+'.hmmlist',self.get_model_name_id()+'.hmmlist')


        tmp_dir = System.get_global_temp_dir()
        with open(os.path.join(tmp_dir,'sil.hed'), 'w') as sil_desc:
            print("""AT 2 4 0.2 {sil.transP}
AT 4 2 0.2 {sil.transP}
AT 1 3 0.3 {sp.transP}
TI silst {sil.state[3],sp.state[2]}
""", file = sil_desc)
        HHEd(self.htk_config,self.get_model_name_id(1)+'.mmf', self.get_model_name_id()+'.mmf',self.get_model_name_id()+'.hmmlist',script=os.path.join(tmp_dir,'sil.hed')).run()
        shutil.rmtree(tmp_dir)

        self.expand_word_transcription(True)

    def transform_to_triphone(self):
        pass

    def tie_triphones(self):
        pass


    def split_mixtures(self,num_mixes):
        pass

    def split_mixtures_variably(self,num_mixes, num_steps, step):
        pass

    def estimate_transform(self):
        pass


