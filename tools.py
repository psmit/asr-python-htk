from itertools import izip

import os
import shutil

from gridscripts.remote_run import JobFailedException, System, SplittableJob,Task,BashJob
from units import HTK_transcription, SCPFile

__author__ = 'peter'


class htk_config(object):
    default_vals = {
        'mix_weight_floor': (float,None),
        'prune_threshold': (float,None),
        'min_examples': (int,None),
        'pruning': (float,[300.0,500.0,2000.0]),
        'num_tokens': (int,None),
        'lm_scale': (float,19.0),             #HDecode
        'beam': (float,250.0),              #HDecode
        'end_beam': (float,None),           #HDecode
        'max_pruning': (int,None),
        'num_speaker_chars': (int,-1),
        'min_variance': (float,0.05),       #HCompV
        'tying_rules': (str,'/share/puhe/peter/rules/phonetic_rules._en'),  #tying
        'tying_threshold': (int, 1000),                                     #tying
        'required_occupation': (int, 200),                                  #tying
        'adap_align_dict': (str, '/share/puhe/peter/dict/cmubeep/dict'),    #adptation
        'ps_power': (float,None),           #training with variable number of mixtures
        'ps_iterations': (int, None),       #training with variable number of mixtures

    }

    def __init__(self, config_file = None, debug_flags = None):
        self.config_file = config_file
        self.debug_flags = debug_flags if debug_flags is not None else []
        self._load_defaults()


    @classmethod
    def add_options_to_optparse(cls,parser):
        for key in cls.default_vals.iterkeys():
            t = "string"
            if cls.default_vals[key][0] == float: t = "float"
            if cls.default_vals[key][0] == int: t = "int"
            parser.add_option("--{0:>s}".format(key), type=t, dest=key)
    
    def _load_defaults(self):
        for key in self.default_vals.iterkeys():
            setattr(self,key,self.default_vals[key][1])

    def load_object_vals(self,o):
        for key in self.default_vals.iterkeys():
            if hasattr(o,key) and getattr(o,key) is not None:
                setattr(self,key,self.default_vals[key][0](getattr(o,key)))

    def load_dict_vals(self,d):
        for key in d.iterkeys():
            if key in self.default_vals:
                setattr(self,key,self.default_vals[key][0](d[key]))

    def load_config_vals(self,config,section="htk_config"):
        for k,v in config.items(section):
            if k in self.default_vals:
                setattr(self,k,self.default_vals[k][0](v))

    def sensible_end_beam(self,beam):
        if self.end_beam is not None:
            return self.end_beam
        elif beam is not None:
            return beam*2.0/3.0
        else:
            return self.beam*2.0/3.0

    def get_flags(self, extra_config_file = None):
        flags = []
        flags.extend(self.debug_flags)
        flags.extend(self.turn_to_config('-C',self.config_file))
        flags.extend(self.turn_to_config('-C',extra_config_file))
        return flags

    @staticmethod
    def turn_to_config(flag,option,type=basestring,default=None):
        if isinstance(option, type):
            return [flag,str(option)]
        elif option is None:
            if default is not None: return [flag,str(default)]
            else: return []
        elif all(isinstance(item,type) for item in option):
            ret_list = []
            for item in option:
                ret_list.extend([flag,str(item)])
            return ret_list
        else:
            raise TypeError()




class HERest(SplittableJob):
    def __init__(self, htk_config, scp_file, hmm_model, hmm_list, input_mlf, config_file = None, input_adaptation = None,
                 parent_adaptation = None, output_adaptation = None, output_hmm_model=None, pruning = None,
                 prune_threshold = None, num_speaker_chars=None, min_examples=None, mix_weight_floor=None, max_adap_sentences = None,
                stats= None):
        super(HERest,self).__init__()

        base_command = ["HERest"]
        base_command.extend(htk_config.get_flags(config_file))

        #task specific flags
        #base_command.extend(htk_config.turn_to_config('-S','{scp_list}'))

        self.acc_tmp_dir = System.get_global_temp_dir()
        # Output dependent flags
        if output_hmm_model is not None:
            base_command.extend(htk_config.turn_to_config('-M', self.acc_tmp_dir))

            #base_command.extend(htk_config.turn_to_config('-M', os.path.dirname(output_hmm_model)))

        if output_adaptation is not None:
            base_command.extend(['-u','a'])
            target_dir, extension = output_adaptation
            base_command.extend(['-K', target_dir])
            if extension is not None:
                base_command.append(extension)


        num_speaker_chars = num_speaker_chars if num_speaker_chars is not None else htk_config.num_speaker_chars

        # Adaptation flags
        if input_adaptation is not None:
            for source_dir, extension in input_adaptation:
                base_command.extend(['-J', source_dir])
                if extension is not None:
                    base_command.append(extension)


        if parent_adaptation is not None:
            for source_dir, extension in parent_adaptation:
                base_command.extend(['-E', source_dir])
                if extension is not None:
                    base_command.append(extension)
            base_command.append('-a')

        if num_speaker_chars > 0:
            pattern = "*/" + ('%' * num_speaker_chars) + "*.*"
            base_command.extend(['-h',pattern])


        #pruning flag
        if pruning is None: pruning = htk_config.pruning
        if isinstance(pruning, float):
            base_command.extend(['-t',pruning])
        elif all(isinstance(p,float) for p in pruning):
            base_command.extend(['-t']+ [str(p) for p in pruning])  
        else:
            raise TypeError
            

        # other flags
        base_command.extend(htk_config.turn_to_config('-I', input_mlf))
        base_command.extend(htk_config.turn_to_config('-H', hmm_model))

        base_command.extend(htk_config.turn_to_config('-w', mix_weight_floor, type=float, default=htk_config.mix_weight_floor))
        base_command.extend(htk_config.turn_to_config('-c', prune_threshold, type=float, default=htk_config.prune_threshold))
        base_command.extend(htk_config.turn_to_config('-m', min_examples, type=int, default=htk_config.min_examples))

        base_command.extend(htk_config.turn_to_config('-l', max_adap_sentences, type=int))


        #positional arguments
        base_command.append(hmm_list)


        #store instance variables
        self.base_command = base_command
        self.hmm_model = hmm_model
        self.output_hmm_model = output_hmm_model
        self.output_adaptation = output_adaptation
        self.scp_file = scp_file
        self.num_speaker_chars = num_speaker_chars
        self.stats = stats

    def _split_to_tasks(self):
        self.scp_tmp_dir = System.get_global_temp_dir()
        scp_files = SCPFile(self.scp_file).split(self.max_num_tasks,self.scp_tmp_dir,
                                                 self.num_speaker_chars if self.num_speaker_chars is not None else -1)

        for i, scp_file in enumerate(scp_files):
            self.tasks.append(HERestTask(self,i+1,scp_file))


    def _merge_tasks(self):
        if not all(task._test_success() for task in self.tasks):
            raise JobFailedException

        if self.output_hmm_model is not None:
            t = HERestTask(self,0)
            t.run()
            if not t._test_success():
                raise JobFailedException

            shutil.copyfile(os.path.join(self.acc_tmp_dir, os.path.basename(self.hmm_model)), self.output_hmm_model)


        if self.cleaning:
            if self.output_hmm_model is not None:
                for task in self.tasks:
                    task._clean()

            shutil.rmtree(self.scp_tmp_dir)
            shutil.rmtree(self.acc_tmp_dir)


class HERestTask(Task,BashJob):
    def __init__(self,parent_job,task_id,scp_file=None):
        super(HERestTask,self).__init__(task_id)
        self.parent = parent_job
        self.task_id = task_id
        self.scp_file = scp_file

        if task_id is 0:
            self.command = [parent_job.base_command[0],'-p',str(self.task_id)] + parent_job.base_command[1:] + [os.path.join(self.parent.acc_tmp_dir,'HER{0:d}.acc'.format(id)) for id in xrange(1,len(self.parent.tasks)+1)]
            if self.parent.stats is not None:
                self.command = [self.command[0],'-s',self.parent.stats]+self.command[1:]
        else:
            self.command = [parent_job.base_command[0],'-S',self.scp_file,'-p',str(self.task_id)] + parent_job.base_command[1:]

    def _test_success(self):
        if self.task_id is 0:
            return os.path.exists(os.path.join(self.parent.acc_tmp_dir, os.path.basename(self.parent.hmm_model)))

        else:
            success = True
            if self.parent.output_hmm_model is not None:
                success = success and os.path.exists(os.path.join(self.parent.acc_tmp_dir,'HER{0:d}.acc'.format(self.task_id)))
            if self.parent.output_adaptation is not None:
                success = success and any(os.path.exists(f) for f in self._get_output_transforms())

            return success

    def _clean(self,keep_input_files=False):

        if not keep_input_files and self.scp_file is not None:
            os.remove(self.scp_file)

        if self.task_id > 0:
            try:
                if self.parent.output_hmm_model is not None:
                    os.remove(os.path.join(self.parent.acc_tmp_dir,'HER{0:d}.acc'.format(self.task_id)))

                for f in self._get_output_transforms():
                    os.remove(f)

            except OSError:
                pass


    def _get_output_transforms(self):
        if self.parent.output_adaptation is None:
            return []

        speakers = set(os.path.basename(s)[:self.parent.num_speaker_chars] for s in open(self.scp_file))
        output_dir, output_extension = self.parent.output_adaptation

        return [os.path.join(output_dir, s + '.'+ output_extension) for s in speakers]

                        

class HDecode(SplittableJob):

    def __init__(self, htk_config, scp_file, hmm_model, dict, hmm_list, language_model, output_mlf, config_file = None,
                 num_tokens = None, lm_scale = None, max_pruning = None, beam = None, end_beam = None, adapt_dirs=None,
                 adapt_speaker_chars = -1, trn_speaker_chars = None, lattice_extension=None):
        super(HDecode,self).__init__()

        base_command = ["HDecode"]
        base_command.extend( htk_config.get_flags(config_file) )


        #task specific flags
#        base_command.extend(htk_config.turn_to_config('-S','{scp_list}'))
#        base_command.extend(htk_config.turn_to_config('-i','{output_mlf}'))


        #adaptation flags
        if adapt_dirs is not None:
            adapt_speaker_chars = adapt_speaker_chars if adapt_speaker_chars is not None else htk_config.num_speaker_chars

            for source_dir, extension in adapt_dirs:
                base_command.extend(['-J', source_dir])
                if extension is not None:
                    base_command.append(extension)

            base_command.append('-m')

            pattern = '*.%%%'
            if adapt_speaker_chars > 0:
                pattern = "*/" + ('%' * adapt_speaker_chars) + "*.*"
            base_command.extend(['-h',pattern])


        #other flags
        base_command.extend(htk_config.turn_to_config('-H',hmm_model))
        base_command.extend(htk_config.turn_to_config('-w',language_model))
        base_command.extend(htk_config.turn_to_config('-n',num_tokens,type=int,default=htk_config.num_tokens))
        base_command.extend(htk_config.turn_to_config('-s',lm_scale,type=float,default=htk_config.lm_scale))
        base_command.extend(htk_config.turn_to_config('-t',beam,type=float,default=htk_config.beam))
        base_command.extend(htk_config.turn_to_config('-v',end_beam,type=float,default=htk_config.sensible_end_beam(beam)))
        base_command.extend(htk_config.turn_to_config('-u',max_pruning,type=int,default=htk_config.max_pruning))
        base_command.extend(htk_config.turn_to_config('-z',lattice_extension))
        base_command.extend(htk_config.turn_to_config('-o','ST'))

        
        #positional arguments
        base_command.extend([dict,hmm_list])


        #store instance variables
        self.scp_file = scp_file
        self.output_mlf = output_mlf

        self.trn_speaker_chars = trn_speaker_chars if trn_speaker_chars is not None else htk_config.num_speaker_chars

        self.base_command = base_command

        self.htk_config = htk_config



    def _split_to_tasks(self):
        self.tmp_dir = System.get_global_temp_dir()
        scp_files = SCPFile(self.scp_file).split(self.max_num_tasks,self.tmp_dir, -1)
#                                                 self.num_speaker_chars if self.num_speaker_chars is not None else -1)

        mlf_files = [scp_file + '.mlf' for scp_file in scp_files]

        for i, files in enumerate(izip(scp_files,mlf_files)):
            scp_file, output_mlf = files
            self.tasks.append(HDecodeTask(self,i+1,scp_file,output_mlf))


    def _merge_tasks(self):

        if not all(task._test_success() for task in self.tasks):
            raise JobFailedException

        tr = HTK_transcription()
        for task in self.tasks:
            tr.read_mlf(task.output_mlf,target=HTK_transcription.WORD)

        tr.write_mlf(self.output_mlf,target=HTK_transcription.WORD)
        tr.write_trn(os.path.splitext(self.output_mlf)[0] + '.trn',speaker_name_width=self.trn_speaker_chars if self.trn_speaker_chars > 0 else self.htk_config.num_speaker_chars)

        if self.cleaning:
            for task in self.tasks:
                task._clean()

            shutil.rmtree(self.tmp_dir)

class HDecodeTask(Task,BashJob):
    def __init__(self,parent_job,task_id,scp_file,output_mlf):
        super(HDecodeTask,self).__init__(task_id)
        self.parent = parent_job
        self.task_id = task_id
        self.scp_file = scp_file
        self.output_mlf = output_mlf

        self.command = [parent_job.base_command[0],'-S',self.scp_file,'-i',self.output_mlf] + parent_job.base_command[1:]

    def _clean(self,keep_input_files=False):
        if not keep_input_files:
            os.remove(self.scp_file)
        os.remove(self.output_mlf)

    def _test_success(self):
        return os.path.exists(self.output_mlf) and len([a for a in open(self.output_mlf) if a.startswith('"/')]) >= len([a for a in open(self.scp_file)])


class HVite(SplittableJob):
    def __init__(self,htk_config, scp_file, hmm_model, dict, hmm_list, output_transcriptions, input_transcriptions, config_file = None, ext='lab', pruning=None):
        super(HVite,self).__init__()
        self.htk_config = htk_config

        base_command = ["HVite"]
        base_command.extend(htk_config.get_flags(config_file))

        base_command.extend(htk_config.turn_to_config('-H',hmm_model))
        base_command.extend(htk_config.turn_to_config('-l','*'))
        base_command.extend(htk_config.turn_to_config('-o','ST'))
        base_command.extend(htk_config.turn_to_config('-x',ext))
        base_command.extend(htk_config.turn_to_config('-y','lab'))
        base_command.extend(htk_config.turn_to_config('-I',input_transcriptions))


        #pruning flag
        if pruning is None: pruning = htk_config.pruning
        if isinstance(pruning, float):
            base_command.extend(['-t',pruning])
        elif all(isinstance(p,float) for p in pruning):
            base_command.extend(['-t']+ [str(p) for p in pruning])
        else:
            raise TypeError


        base_command.append('-a')
        base_command.append('-m')

        base_command.append(dict)
        base_command.append(hmm_list)
#
#        "-S", scp_file+ ".part.%t",
#                    "-i", new_transcriptions + ".part.%t",

#    HVite.extend(extra_HTK_options)
#
#
#    HVite.extend(["-t"])
#    HVite.extend(pruning)
#

        #store instance variables
        self.scp_file = scp_file
        self.output_mlf = output_transcriptions
        self.base_command = base_command

    def _split_to_tasks(self):
        self.tmp_dir = System.get_global_temp_dir()
        scp_files = SCPFile(self.scp_file).split(self.max_num_tasks,self.tmp_dir, -1)

        mlf_files = [scp_file + '.mlf' for scp_file in scp_files]

        for i, files in enumerate(izip(scp_files,mlf_files)):
            scp_file, output_mlf = files
            self.tasks.append(HViteTask(self,i+1,scp_file,output_mlf))

    def _merge_tasks(self):

        if not all(task._test_success() for task in self.tasks):
            raise JobFailedException

        tr = HTK_transcription()
        for task in self.tasks:
            tr.read_mlf(task.output_mlf)

        tr.write_mlf(self.output_mlf)
        
        if self.cleaning:
            for task in self.tasks:
                task._clean()

            shutil.rmtree(self.tmp_dir)


class HViteTask(Task,BashJob):
    def __init__(self,parent_job,task_id,scp_file,output_mlf):
        super(HViteTask,self).__init__(task_id)
        self.parent = parent_job
        self.task_id = task_id
        self.scp_file = scp_file
        self.output_mlf = output_mlf

        self.command = [parent_job.base_command[0],'-S', self.scp_file , '-i', self.output_mlf] + parent_job.base_command[1:]

    def _clean(self,keep_input_files=False):
        if not keep_input_files:
            os.remove(self.scp_file)
        os.remove(self.output_mlf)

    def _test_success(self):
        return os.path.exists(self.output_mlf) and len([a for a in open(self.output_mlf) if a.startswith('"')]) == len([a for a in open(self.scp_file)])


    
class HLEd(BashJob):
    def __init__(self, htk_config, input_transcriptions, led_file, phones_list, dict, output_transcriptions, selector = '*' ):
        super(HLEd,self).__init__()
        command = ['HLEd']
        command.extend(htk_config.get_flags())

        command.extend(htk_config.turn_to_config('-d', dict))
        command.extend(htk_config.turn_to_config('-n', phones_list))
        command.extend(htk_config.turn_to_config('-l', selector))
        command.extend(htk_config.turn_to_config('-i', output_transcriptions))

        command.append(led_file)
        command.append(input_transcriptions)
        self.command = command


class HCompV(BashJob):
    def __init__(self, htk_config, scp_file, proto_file, min_variance = None):
        super(HCompV,self).__init__()
        command = ['HCompV']
        command.extend(htk_config.get_flags())
        command.extend(htk_config.turn_to_config('-M', os.path.dirname(proto_file)))

        command.extend(htk_config.turn_to_config('-S', scp_file))
        command.extend(htk_config.turn_to_config('-f', min_variance, type=float,default=htk_config.min_variance))
        command.append('-m')

        command.append(proto_file)

        self.command = command
        

class HHEd(BashJob):
    def __init__(self, htk_config, input_model, output_model, hmm_list, script=None, binary=False):
        super(HHEd,self).__init__()
        self.htk_config = htk_config

        command = ['HHEd']
        command.extend(htk_config.get_flags())
        command.extend(htk_config.turn_to_config('-H', input_model))
#        command.extend(htk_config.turn_to_config('-M', os.path.dirname(output_model)))
        if os.path.isdir(output_model):
            command.extend(htk_config.turn_to_config('-M', output_model))
        else:
            command.extend(htk_config.turn_to_config('-w', output_model))

        if binary:
            command.append('-B')

        if script is None:
            script = '/dev/null'
        command.append(script)
        command.append(hmm_list)

        self.command = command


class Copier(object):
    def __init__(self,target_dir):
        self.target_dir = target_dir
    def __call__(self,src):
        shutil.copyfile(src, os.path.join(self.target_dir,os.path.basename(src)))