from __future__ import print_function
import os


class HTK_dictionary(object):
    fixed_values = {'<s>':set(['sil']), '</s>':set(['sil'])}

    def __init__(self):
        self.dictionary = {}

    def write_dict(self,file_name,hvite=True):
        self.dictionary.update(self.fixed_values)

        with open(file_name,'w') as file_desc:
            for word in sorted(self.dictionary.iterkeys()):
                for transcription in self.dictionary[word]:
                    if word.startswith('<'):
                        print("{0:s}\t{1:s}".format(word," ".join(transcription)),file=file_desc)
                    elif hvite:
                        print("{0:s}\t{1:s} sp".format(word," ".join(transcription)),file=file_desc)
                        print("{0:s}\t{1:s} sil".format(word," ".join(transcription)),file=file_desc)
                    else:
                        print("{0:s}\t{1:s}".format(word," ".join(transcription)),file=file_desc)

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
        return phones

    def _add_transcription(self,word,transcription):
        if word not in self.dictionary:
            self.dictionary[word] = set()

        while transcription[-1] in ["sp", "sil"]:
            transcription = transcription[:-1]

        self.dictionary[word].add(tuple(transcription))


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
                cur_file_name = os.path.splitext(os.path.basename(line.strip()[1:-1]))[0]
                cur_transcription = []
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


class SCPFile(object):
    def __init__(self,file):
        self.file = file

    def split(self,num_parts,dir,prefix_length=-1):
        parts = []
        for i in xrange(num_parts): parts.append([])

        prev_file = ""
        cur_index = -1

        for file in sorted(f.strip() for f in open(self.file)):
            if prefix_length < 0 or os.path.basename(file)[:prefix_length] != prev_file[:prefix_length]:
                cur_index = (cur_index + 1) % len(parts)
            parts[cur_index].append(file)
            prev_file = file

        scp_files = []
        for i in xrange(num_parts):
            if len(parts[i]) > 0:
                scp_file = 'scp.%d'% (i+1)
                with open(os.path.join(dir, scp_file), 'w') as scp_desc:
                    for file in parts[i]:
                        print(file, file=scp_desc)
                scp_files.append(os.path.join(dir, scp_file))
            else:
                break
        return scp_files
