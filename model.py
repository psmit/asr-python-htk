from __future__ import print_function
import glob
import os
import shutil
from tools import System, HCompV, htk_config, HERest, HHEd


__author__ = 'peter'

class ExistingFilesException(Exception): pass

class TrainLogger(object):
    a = []
    def __init__(self,f):
        self.f = f
        self.__name__ = f.__name__

    def __call__(self,*args,**kwargs):
        print("Calling %s" % self.__name__)
        self.a.append(self.__name__)
        self.f(self, *args,**kwargs)


class HTK_model(object):
    def __init__(self, name, model_dir):
        self.name = name

        self.model_dir = model_dir
        self.train_files_dir = os.path.join(self.model_dir, self.name)

        self.training_scp = os.path.join(self.train_files_dir, 'train.scp')
        self.training_word_mlf = os.path.join(self.train_files_dir, 'word.mlf')
        self.training_phone_mlf = os.path.join(self.train_files_dir, 'phone.mlf')
        self.training_dict = os.path.join(self.train_files_dir,'dict')

        self.htk_config = htk_config()
        self.training_files_speaker_name_chars = 3

        self.phones = []
        self.id = None


    def get_model_name_id(self,prev=0):
        id = self.id-prev
        return self.model_dir + '/' + "{0}.{1:02d}".format(self.name,id)
    

    def initialize_new(self, scp_list, word_mlf, dict, remove_previous=False):
        if not remove_previous and (os.path.exists(self.train_files_dir) or len(glob.iglob(self.model_dir + '/' + self.name + '.*')) > 0):
            raise ExistingFilesException

        if os.path.exists(self.train_files_dir): shutil.rmtree(self.train_files_dir)
        for f in glob.iglob(self.model_dir + '/' + self.name + '.*'): os.remove(f)
        os.mkdir(self.train_files_dir)

        # handle scp files
        if isinstance(scp_list,basestring):
            shutil.copyfile(scp_list,self.training_scp)
        elif all(isinstance(scp,basestring) for scp in scp_list):
            with open(self.training_scp, 'w') as scp_desc:
                for scp in scp_list:
                    for file in open(scp):
                        print(file.strip(),file=scp_desc)
        else:
            raise TypeError


        # handle dictionary
        dic = HTK_dictionary()
        if isinstance(dict,basestring):
            dic.read_dict(dic)
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
        trans.write_mlf(self.training_word_mlf)

        self.id = 1

        phones_list = self.get_model_name_id() + '.hmmlist'
        with open(phones_list, 'w') as phones_desc:
            for p in self.phones:
                print(p, file=phones_desc)


    def initialize_existing(self):
        pass

    def flat_start(self):
        tmp_dir = System.get_global_temp_dir()
        proto_file = os.path.join(tmp_dir, 'proto')
        vFloors = os.path.join(tmp_dir, 'vFloors')
        HCompV(self.htk_config, self.training_scp, proto_file)()


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
                print(line, file=model_desc)

            #Write the hmmdefs  (replacing for each monophone, proto with the monophone)
            for line in open( self.get_model_name_id() + '.hmmlist'):
                print(phone_def.replace('proto', line.rstrip()), file=model_desc)
                
        shutil.rmtree(tmp_dir)
        
    def re_estimate(self):
        self.id += 1
        shutil.copyfile(self.get_model_name_id(1)+'.hmmlist',self.get_model_name_id()+'.hmmlist')
        HERest(self.htk_config, self.training_scp,self.get_model_name_id(1)+'.mmf',self.get_model_name_id()+'.hmmlist',
               self.training_phone_mlf,output_hmm_model=self.get_model_name_id()+'.mmf')()


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

        with open(self.get_model_name_id()+'.mmf') as model_desc:
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
        with open(os.path.join(tmp_dir,'sil.hed')) as sil_desc:
            print("""AT 2 4 0.2 {sil.transP}
AT 4 2 0.2 {sil.transP}
AT 1 3 0.3 {sp.transP}
TI silst {sil.state[3],sp.state[2]}
""", file = sil_desc)
        HHEd(self.htk_config,self.get_model_name_id(1)+'.mmf', self.get_model_name_id(0)+'.mmf',self.get_model_name_id()+'.hmmlist',script=sil_desc)()
        shutil.rmtree(tmp_dir)



    def transform_to_triphone(self):
        pass

    def tie_triphones(self):
        pass


    
    @TrainLogger
    def split_mixtures(self,num_mixes):
        pass

    @TrainLogger
    def split_mixtures_variably(self,num_mixes, num_steps, step):
        pass

    @TrainLogger
    def estimate_transform(self):
        pass





class HTK_dictionary(object):
    fixed_values = {'<s>':set(['sil']), '</s>':set(['sil'])}

    def __init__(self):
        self.dictionary = {}

    def write_dict(self,file_name,hvite=True):
        self.dictionary.update(self.fixed_values)

        with open(file_name,'w') as file_desc:
            for word in self.dictionary.iterkeys():
                for transcription in self.dictionary[word]:
                    if word.startswith('<'):
                        print("{1:s}\t{2:s}".format(word," ".join(transcription)),file=file_desc)
                    elif hvite:
                        print("{1:s}\t{2:s} sp".format(word," ".join(transcription)),file=file_desc)
                        print("{1:s}\t{2:s} sil".format(word," ".join(transcription)),file=file_desc)
                    else:
                        print("{1:s}\t{2:s}".format(word," ".join(transcription)),file=file_desc)

    def read_dict(self,file_name):
        for line in open(file_name):
            parts = line.split()
            self._add_transcription(parts[0],parts[1:])

    def get_phones(self):
        phones = set()
        for word in self.dictionary.iterkeys():
            for trans in self.dictionary[word]:
                for t in trans:
                    phones.add(t)

    def _add_transcription(self,word,transcription):
        if word not in self.dictionary:
            self.dictionary[word] = set()

        while transcription[-1] in ["sp", "sil"]:
            transcription = transcription[:-1]

        self.dictionary[word].add(transcription)


class HTK_transcription(object):
    WORD = 0
    PHONE = 1
    STATE = 2

    def __init__(self):
        self.transcriptions = {}


    def expand_words_to_phones(self,model,use_sp,use_triphones):
        script = ""
        if use_triphones:
            script = "ME sil sil sil\nWB sp\nNB sp\nTC sil sil\n"
        else:
            script = "EX\nIS sil sil\n"
            if not use_sp:
                script += "DE sp\n"

        model.htk.HLEd(self,model.dict,script)


    def align_phone_transcriptions(self, model):
        pass


    def read_mlf(self, mlf_file, target=PHONE):
        cur_file_name = None
        cur_transcription = []

        if target not in self.transcriptions:
            self.transcriptions[target] = {}

        for line in open(mlf_file):
            if line.startswith("#"): continue
            elif line.startswith("\""):
                cur_file_name = os.path.splitext(os.path.basename(line.strip()[1:-1]))
            elif line.startswith("."):
                self.transcriptions[target][cur_file_name] = cur_transcription
            else:
                if target < HTK_transcription.STATE:
                    cur_transcription.append(line.split()[0])
                else:
                    start,end,state = line.split()[:3]
                    cur_transcription.append((int(start),int(end),state))

    def write_mlf(self, mlf_file, target=PHONE, extension="lab"):
        with open(mlf_file, 'w') as mlf_desc:
            print("#!MLF!#",file=mlf_desc)

            for file_name in self.transcriptions[target].iterkeys():
                print("\"*/{0:>s}.{1:>s}\"".format(file_name,extension),file=mlf_desc)

                for part in self.transcriptions[target][file_name]:
                    print(part,file=mlf_desc)
                print(".",file=mlf_desc)

    def read_trn(self, trn_file):
        target = HTK_transcription.PHONE

        if target not in self.transcriptions:
            self.transcriptions[target] = {}

        for line in open(trn_file):
            parts = line.split()
            self.transcriptions[target][parts[-1][1:-1].replace('_','')] = parts[:-1]

    def write_trn(self, trn_file, speaker_name_width = -1):
        target = HTK_transcription.PHONE

        with open(trn_file, 'w') as trn_desc:
            for file_name in self.transcriptions[target].iterkeys():
                if speaker_name_width > 0:
                    file_name = file_name[:speaker_name_width] + '_' + file_name[speaker_name_widte_h:]
                print("{1:s} ({2:s})".format(" ".join(self.transcriptions[target][file_name]), filname))


