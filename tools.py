from datetime import time
from itertools import izip
import os
import shutil
import sys
import tempfile
from model import HTK_transcription

__author__ = 'peter'


class JobFailedException(Exception): pass

class TaskFailedException(Exception): pass

class System(object):
    @staticmethod
    def get_global_temp_dir():
        try:
            return tempfile.mkdtemp(dir=os.environ['GLOBAL_TMP'])
        except KeyError:
            sys.exit("Please set the GLOBAL_TMP environment variable to a directory for temporary files")

    @staticmethod
    def get_local_temp_dir():
        try:
            return tempfile.mkdtemp(dir=os.environ['LOCAL_TMP'])
        except KeyError:
            sys.exit("Please set the LOCAL_TMP environment variable to a directory for temporary files")
        except OSError:
            sys.exit("The LOCAL_TMP directory does not seem to exist")


class Job(object):
    max_num_retries = 2
    cleaning = True

    def _run(self):
        pass

    def __call__(self):
        self._run()




class AtomicJob(Job):
    pass


class Task(object):
    max_task_retries = 3

    def _run(self):
        raise TaskFailedException

    def _clean(self,keep_input_files=False):
        pass

    def __call__(self):
        tries = 0
        while True:
            try:
                self._run()
            except TaskFailedException:
                if tries < self.max_task_retries:
                    tries += 1
                    self._clean(keep_input_files=True)
                else:
                    raise
            else:
                return

    def _test_success(self):
        return True


class SplittableJob(Job):
    max_num_tasks = 10

    def __init__(self):
        self.tasks = []

    def _split_to_tasks(self):
        pass

    def _merge_tasks(self):
        pass

    def __call__(self):
        self._split_to_tasks()

        try:
            for task in self.tasks:
                task()

            self._merge_tasks()

        except TaskFailedException:
            raise JobFailedException



class htk_config(object):
    default_vals = {
        'mix_weight_floor': (float,None),
        'prune_threshold': (float,None),
        'min_examples': (int,None),
        'pruning': (float,None),
        'num_tokens': (int,None),
        'lm_scale': (int,None),
        'beam': (float,200.0),
        'end_beam': (float,None),
        'max_pruning': (int,None),
        'num_speaker_chars': (int,-1),
        'min_variance': (float,None),
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
            return [flag,option]
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
                 prune_threshold = None, num_speaker_chars=None, min_examples=None, mix_weight_floor=None, max_adap_sentences = None ):
        super(HERest,self).__init__()

        base_command = ["HERest"]
        base_command.extend(htk_config.get_flags(config_file))

        #task specific flags
        #base_command.extend(htk_config.turn_to_config('-S','{scp_list}'))


        # Output dependent flags
        if output_hmm_model is not None:
            self.acc_tmp_dir = System.get_global_temp_dir()
            base_command.extend(htk_config.turn_to_config('-M', self.acc_tmp_dir))

            #base_command.extend(htk_config.turn_to_config('-M', os.path.dirname(output_hmm_model)))

        if output_adaptation is not None:
            base_command.extend(['-u','a'])
            #TODO: add output adaptation dirs


        num_speaker_chars = num_speaker_chars if num_speaker_chars is not None else htk_config.num_speaker_chars

        # Adaptation flags
        if input_adaptation is not None:
            for source_dir, extension in input_adaptation:
                base_command.extend(['-J', source_dir])
                if extension is not None:
                    base_command.append(extension)
            base_command.append('-a')

        if parent_adaptation is not None:
            for source_dir, extension in parent_adaptation:
                base_command.extend(['-E', source_dir])
                if extension is not None:
                    base_command.append(extension)

        if num_speaker_chars > 0:
            pattern = "*/" + ('%' * num_speaker_chars) + "*.*"
            base_command.extend(['-h',pattern])


        #pruning flag
        if pruning is None: pruning = htk_config.pruning
        if isinstance(pruning, float):
            base_command.extend(['-t',pruning])
        elif all(isinstance(p,float) for p in pruning):
            base_command.extend(['-t', ' '.join(str(p) for p in pruning)])
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
        base_command.extend(hmm_list)


        #store instance variables
        self.base_command = base_command
        self.hmm_model = hmm_model
        self.output_hmm_model = output_hmm_model
        self.output_adaptation = output_adaptation
        self.scp_file = scp_file
        self.num_speaker_chars = num_speaker_chars

    def _split_to_tasks(self):
        self.scp_tmp_dir = System.get_global_temp_dir()
        scp_files = SCPFile(self.scp_file).split(self.max_num_tasks,self.scp_tmp_dir,
                                                 self.num_speaker_chars if self.num_speaker_chars is not None else -1)

        for i, scp_file in enumerate(scp_files):
            self.tasks.append(HERest.HERestTask(self,i+1,self.scp_file))


    def _merge_tasks(self):
        if not all(task._test_success() for task in self.tasks):
            raise JobFailedException

        if self.output_hmm_model is not None:
            t = HERest.HERestTask(self,0)
            t()
            if not t._test_success():
                raise JobFailedException

            shutil.copyfile(os.path.join(self.acc_tmp_dir, os.path.basename(self.hmm_model)), self.output_hmm_model)


        if self.cleaning:
            for task in self.tasks:
                task._clean()

            shutil.rmtree(self.scp_tmp_dir)
            shutil.rmtree(self.acc_tmp_dir)


    class HERestTask(Task):
        def __init__(self,parent_job,task_id,scp_file=None):
            self.parent = parent_job
            self.task_id = task_id
            self.scp_file = scp_file

        def _run(self):
            localized_command = [cmd_part.format({'scp_file':self.scp_file})
                                 for cmd_part in self.parent.base_command]

            print ' '.join(localized_command)

        def _test_success(self):
            success = True
            if self.parent.output_hmm_model is not None:
                success = success and os.path.exists(os.path.join(os.path.dirname(self.parent.output_hmm_model),self.task_id+'.acc'))
            if self.parent.output_adaptation is not None:
                success = success and any(os.path.exists(f) for f in self._get_output_transforms())

            return success

        def _clean(self,keep_input_files=False):

            if not keep_input_files and self.scp_file is not None:
                os.remove(self.scp_file)

            if self.task_id > 0:
                try:
                    if self.parent.output_hmm_model is not None:
                        os.remove(os.path.join(os.path.dirname(self.parent.output_hmm_model),self.task_id+'.acc') )

                    for f in self._get_output_transforms():
                        os.remove(f)

                except OSError:
                    pass


        def _get_output_transforms(self):
            if self.parent.output_adaptation is None:
                return []

            speakers = set(s[:self.parent.num_speaker_chars] for s in open(self.scp_file))
            output_dir, output_extension = self.parent.output_adaptation

            return [os.path.join(output_dir, s + '.'+ output_extension) for s in speakers]

                        

class HDecode(SplittableJob):

    def __init__(self, htk_config, scp_file, hmm_model, dict, hmm_list, language_model, output_mlf, config_file,
                 num_tokens = None, lm_scale = None, max_pruning = None, beam = None, end_beam = None, adapt_dirs=None,
                 num_speaker_chars=None ,lattice_extension=None):
        super(HDecode,self).__init__()

        base_command = ["HDecode"]
        base_command.extend(htk_config.get_flags(config_file))


        #task specific flags
        base_command.extend(htk_config.turn_to_config('-S','{scp_list}'))
        base_command.extend(htk_config.turn_to_config('-i','{output_mlf}'))


        #adaptation flags
        if adapt_dirs is not None:
            num_speaker_chars = num_speaker_chars if num_speaker_chars is not None else htk_config.num_speaker_chars

            for source_dir, extension in adapt_dirs:
                base_command.extend(['-J', source_dir])
                if extension is not None:
                    base_command.append(extension)

            base_command.append('-m')

            pattern = '*.%%%'
            if num_speaker_chars > 0:
                pattern = "*/" + ('%' * num_speaker_chars) + "*.*"
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
        self.num_speaker_chars = num_speaker_chars

        self.base_command = base_command



    def _split_to_tasks(self):
        self.tmp_dir = System.get_global_temp_dir()
        scp_files = SCPFile(self.scp_file).split(self.max_num_tasks,self.tmp_dir,
                                                 self.num_speaker_chars if self.num_speaker_chars is not None else -1)

        mlf_files = [os.path.splitext(scp_file)[0] + '.mlf' for scp_file in scp_files]

        for i, files in enumerate(izip(scp_files,mlf_files)):
            scp_file, output_mlf = files
            self.tasks.append(HDecode.HDecodeTask(self,i+1,scp_file,output_mlf))


    def _merge_tasks(self):

        if not all(task._test_success() for task in self.tasks):
            raise JobFailedException

        tr = HTK_transcription()
        for task in self.tasks:
            tr.read_mlf(task.output_mlf)

        tr.write_mlf(self.output_mlf)
        tr.write_trn(os.path.splitext(self.output_mlf)[0] + '.trn')

        if self.cleaning:
            for task in self.tasks:
                task._clean()

            shutil.rmtree(self.tmp_dir)

    class HDecodeTask(Task):
        def __init__(self,parent_job,task_id,scp_file,output_mlf):
            self.parent = parent_job
            self.task_id = task_id
            self.scp_file = scp_file
            self.output_mlf = output_mlf

        def _run(self):
            localized_command = [cmd_part.format({'scp_file':self.scp_file,'output_mlf':self.output_mlf})
                                 for cmd_part in self.parent.base_command]

            print ' '.join(localized_command)

        def _clean(self,keep_input_files=False):
            if not keep_input_files:
                os.remove(self.scp_file)
            os.remove(self.output_mlf)
        def _test_success(self):
            return os.path.exists(self.output_mlf) and len(a for a in open(self.output_mlf) if a.startswith('"')) == len(open(self.scp_file))


    
class HLEd(AtomicJob):
    def __init__(self, htk_config):
        super(HLEd,self).__init__()
        self.htk_config = htk_config


class HCompV(AtomicJob):
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

    def _run(self):
        print ' '.join(self.command)
        

class HHEd(AtomicJob):
    def __init__(self, htk_config, input_model, output_model, hmm_list, script=None, binary=False):
        super(HHEd,self).__init__()
        self.htk_config = htk_config

        command = ['HHEd']
        command.extend(htk_config.get_flags())
        command.extend(htk_config.turn_to_config('-H', input_model))
        command.extend(htk_config.turn_to_config('-w', output_model))

        if binary:
            command.append('-B')

        if script is None:
            script = '/dev/null'
        command.append(script)
        command.append(hmm_list)

        self.command = command

    def _run(self):
        print ' '.join(self.command)

class HVite(SplittableJob):
    def __init(self,htk_config):
        super(HVite,self).__init__()
        self.htk_config = htk_config

        

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
                cur_index += 1
            parts[cur_index].append(file)
            prev_file = file

        scp_files = []
        for i in xrange(num_parts):
            if len(parts[i]) > 0:
                scp_file = 'scp.%d'% i+1
                with open(os.path.join(dir, scp_file), 'w') as scp_desc:
                    for file in parts[i]:
                        print >> scp_desc, file
                scp_files.append(scp_file)
            else:
                break
        return scp_files
