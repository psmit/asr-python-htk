#!/usr/bin/env python2.6
from ConfigParser import SafeConfigParser
import multiprocessing
import copy
import optparse
import os
import shutil
import sys

import subprocess


import htk

import data_manipulation
#import job_runner
import job_runner


pool = None

class Model(object):
    configuration = {
        'model_dir': '',
        'lm': '',
        'lm_rescore': None,
        'config': '',
        'recognize_scp': '|MODEL|/files/eval.scp',
        'recognize_mlf': '|MODEL|/files/words.mlf',
        'dict_hdecode': '|MODEL|/dictionary/dict.hdecode',
        'dict_hvite': '|MODEL|/dictionary/dict',
        'tiedlist': '|MODEL|/files/tiedlist',
        'ref_del_char': None,
        'word_suffix': None,
        'speaker_name_width': 5,
    }

    def __init__(self,config=None):
        if config is not None:
            for key in self.configuration.iterkeys():
                if config.get('model',key) is not None:
                    t = type(self.configuration[key]) if self.configuration[key] is not None else str
                    self.configuration[key] =t(config.get('model',key))
                if self.configuration[key] == "":
                    raise Exception("Config Exception: [model] / %s not set" % key)
            self.replace_config_vars()

    def replace_config_vars(self):
        for key in self.configuration.keys():
            if type(self.configuration[key]) == type(""):
                if '|MODEL|' in self.configuration[key]:
                    self.configuration[key] = self.configuration[key].replace('|MODEL|',self.configuration['model_dir'])

class Experiment(object):
    configuration = {
        'model_name': 'hmm_si',
        'lm_scale': 19,
        'beam': 250,
        'end_beam': -1,
        'num_tokens': 32,
        'max_pruning': 40000,
    }

    launch_options = {}
    dependencies = None
    adaptations = None

    done = False
    name = "exp"
    fail_count = 0


    def __init__(self, name='exp', model=None):
        self.name=name.replace('|','').replace('/','')
        self.model=model

    def write(self):
        work_dir = self.name
        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.mkdir(work_dir)

    def run(self):
#        with open(self.name + '/outtest', 'w') as o:
#            print >> o, self.configuration
        work_dir = self.name

        xforms_dir = work_dir + '/xforms'
        classes_dir = work_dir + '/classes'


        model = self.model.configuration['model_dir'] + '/' + self.configuration['model_name']
        recog_scp = work_dir +"/recog.scp"
        shutil.copyfile(self.model.configuration['recognize_scp'], recog_scp)
        #dict_hvite = self.model.configuration['dict_hvite']
        dict_hdecode = self.model.configuration['dict_hdecode']
        tiedlist = self.model.configuration['tiedlist']
        lm = self.model.configuration['lm']
        lm_rescore = self.model.configuration['lm_rescore']
        lm_scale = self.configuration['lm_scale']
        beam = self.configuration['beam']
        end_beam = self.configuration['end_beam']
        max_pruning = self.configuration['max_pruning']
        num_tokens = self.configuration['num_tokens']
        hdecode_mlf = work_dir + '/hdecode.mlf'
        rescore_mlf = work_dir + '/rescore.mlf'
        recog_trn =  work_dir + '/recog.trn'
        configs =  [self.model.configuration['config']]
        speaker_name_width = self.model.configuration['speaker_name_width']
#        adaptation_dir=work_dir + '/xforms'


        try:

            #if os.path.exists(work_dir): shutil.rmtree(work_dir)




            htk_lat_dir = os.path.join(work_dir, 'lattices.htk')
            rescore_lat_dir = os.path.join(work_dir, 'lattices.rescore')
            log_dir = os.path.join(work_dir, 'log')
            for dir in [work_dir, htk_lat_dir, rescore_lat_dir, log_dir, xforms_dir, classes_dir]:
                if not os.path.exists(dir):
                    os.mkdir(dir)

            current_parent_transform = None
            for i, adaptation in enumerate(self.adaptations):
                current_parent_transform = adaptation.make_adaptation(i,current_parent_transform,self)

            adap_dirs = None
            speaker_name_width = 3
            if current_parent_transform is not None:
                configs.append(current_parent_transform[1])
                extension = current_parent_transform[0]
                adap_dirs = [(xforms_dir, extension),(classes_dir, None)]
                speaker_name_width = current_parent_transform[2]

            print "Start step: %d (%s)" % (0, 'Generating lattices with HDecode')
            htk.HDecode(log_dir, recog_scp, model, dict_hdecode, tiedlist, lm, htk_lat_dir, num_tokens,
                        hdecode_mlf, configs, lm_scale, beam, end_beam, max_pruning, adap_dirs, speaker_name_width)

            if lm_rescore is not None:
                print "Start step: %d (%s)" % (0, 'Rescoring lattices with lattice-tool')
                htk.lattice_rescore(log_dir, htk_lat_dir, rescore_lat_dir, lm_rescore + '.gz', lm_scale)


                print "Start step: %d (%s)" % (0, 'Decoding lattices with lattice-tool')
                htk.lattice_decode(log_dir, rescore_lat_dir, rescore_mlf, lm_scale)
                data_manipulation.mlf_to_trn(rescore_mlf, recog_trn, speaker_name_width)

            else:
                data_manipulation.mlf_to_trn(hdecode_mlf, recog_trn, speaker_name_width)



            self.done = True
            return
        except Experiment:
            self.done = False
        pass
        
    def replace_config_vars(self):
        self.dependencies = set()
        for key in self.configuration.keys():
            if type(self.configuration[key]) == type(""):
                if '|MODEL|' in self.configuration[key]:
                    self.configuration[key].replace('|MODEL|',self.model.configuration['model_dir'])

                l = 0
                r = 100
                while l >=0 and r >= l+2:
                    l = self.configuration[key].find('|EXP')
                    r = self.configuration[key].find('|',l+5)
                    if l >= 0 and r >= l +2:
                        dependency = self.configuration[key][l+5:r]
                        self.dependencies.add(dependency)
                        self.configuration[key] = self.configuration[key].replace('|EXP_%s|' % dependency, dependency)
                    
        for adaptation in self.adaptations:
            self.dependencies = self.dependencies.union(adaptation.dependencies)
            for key in adaptation.configuration.keys():
                if type(adaptation.configuration[key]) == type(""):
                    if '|MODEL|' in adaptation.configuration[key]:
                        adaptation.configuration[key].replace('|MODEL|',self.model.configuration['model_dir'])

                    l = 0
                    r = 100
                    while l >=0 and r >=l+2:
                        l = adaptation.configuration[key].find('|EXP')
                        r = adaptation.configuration[key].find('|',l+5)
                        if l >= 0 and r >= l +2:
                            dependency = adaptation.configuration[key][l+5:r]
                            self.dependencies.add(dependency)
                            adaptation.dependencies.add(dependency)
                            adaptation.configuration[key] = adaptation.configuration[key].replace('|EXP_%s|' % dependency, dependency)
        if self.configuration['end_beam'] < 0:
            self.configuration['end_beam'] = self.configuration['beam'] / 3 * 2
        return

    def are_dependencies_ok(self, experiments):
        for dependency in self.dependencies:
            if not experiments[dependency].done:
                return False
        return True

    def create_exp_dir(self):
        work_dir = self.name
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        os.mkdir(work_dir)

        config = SafeConfigParser()
        config.add_section('model')
        for k,v in self.model.configuration.items():
            config.set('model', k, str(v))

        n_section = "exp_%s" % self.name
        config.add_section(n_section)
        for k,v in self.configuration.items():
            config.set(n_section, k, str(v))

        for i, adaptation in enumerate(self.adaptations):
            j = i + 1
            for k,v in adaptation.configuration.items():
                if len(str(v)) > 0:
                    config.set(n_section, 'adap%d_%s' % (j,k), str(v))

        with open('%s/config' % work_dir, 'wb') as config_file:
            config.write(config_file)

        self.done = True

    def launch_subprocess(self):
        print "Launching %s" % self.name
        command =  [sys.argv[0]]
        #print ' '.join(command)
        for k,v in self.launch_options.items():
            if not k.startswith('recognition') and len(str(v)) > 0:
                command.extend(['--'+str(k).replace('_','-'), str(v)])
        command.extend(['--dir', self.name])
        print ' '.join(command)
        #returncode = subprocess.call(command)
        returncode = 0

        if returncode == 0:
            self.done = True


    def __call__(self):
        self.create_exp_dir()
        self.launch_subprocess()

        return (self.name,self.done)
        
   
class Adaptation(object):
    configuration = {
        'type': 'base',
        'scp': '',
        'mlf': '',
        'mlf_ext': 'rec',
        'nodes': 128,
        'occupation': 1000,
        'num_sentences': 'all',
        'model_hvite': 'hmm_si',
        'model_adapt': 'hmm_si',
        'speaker_name_width': 3,
        'num_adaptation_samples': -1,
    }

    dependencies = set()

    name = 'adaptation'

#    def __copy__(self):
#        ada = Adaptation(self.name)
#        ada.configuration = copy.deepcopy(self.configuration)
#        ada.dependencies = copy.copy(self.dependencies)

    def __deepcopy__(self, memo):
        ada = Adaptation(self.name)
        ada.configuration = copy.deepcopy(self.configuration, memo)
        ada.dependencies = copy.deepcopy(self.dependencies, memo)
        return ada


    def __init__(self, name='adaptation'):
        self.name=name

    def make_adaptation(self, id, parent_transform, experiment):
        work_dir = experiment.name
        classes_dir = work_dir + '/classes'
        xforms_dir = work_dir + '/xforms'
        files_dir = work_dir + '/files'

        target_extension = 'mllr%d' % id
        source_extension = None
        if parent_transform is not None:
            source_extension = parent_transform[0]

        scp_file = self.configuration['scp']
        if scp_file is None or len(scp_file) == 0:
            scp_file = work_dir + '/recog.scp'

        adap_scp = work_dir +"/adap%d.scp" %id
        data_manipulation.copy_scp_file(scp_file, adap_scp)
#        shutil.copyfile(scp_file, adap_scp)

        model_hvite = experiment.model.configuration['model_dir'] + '/' + self.configuration['model_hvite']
        model_adapt = experiment.model.configuration['model_dir'] + '/' + self.configuration['model_adapt']

        phones_list = experiment.model.configuration['model_dir'] + '/files/tiedlist'
        dict_hvite = experiment.model.configuration['dict_hvite']
        source_mlf = self.configuration['mlf']
        source_mlf_ext = self.configuration['mlf_ext']
        adapt_mlf = work_dir + '/adap%d.mlf'%id
        num_nodes = self.configuration['nodes']

        hvite_config = experiment.model.configuration['model_dir'] + '/config/config'
        standard_config = experiment.model.configuration['config']
        adapt_config = files_dir + '/adapt%d.config' % id

        speaker_name_width = self.configuration['speaker_name_width']
        num_adaptation_samples = None
        if self.configuration['num_adaptation_samples'] >= 0:
            num_adaptation_samples = self.configuration['num_adaptation_samples']


        # align transcription
        htk.HVite(0, adap_scp, model_hvite, dict_hvite, phones_list, source_mlf, adapt_mlf, source_mlf_ext, hvite_config)

        if self.configuration['type'] == 'tree':
            regtree_hed = files_dir + '/regtree%d.hed'%id
            regtree = classes_dir+'/regtree%d.tree'%id

            data_manipulation.write_regtree_hed_file(regtree_hed, model_adapt, num_nodes, 'regtree%d'%id)
            data_manipulation.write_tree_cmlllr_config(adapt_config, regtree, '"IntVec 3 13 13 13"')

            htk.HHEd(0, model_adapt, classes_dir, regtree_hed, phones_list, '/dev/null')


            htk.HERest_estimate_transform(0, adap_scp, model_adapt, xforms_dir, phones_list, adapt_mlf,
                                          num_adaptation_samples,
                                          [standard_config, adapt_config], speaker_name_width, target_extension,
                                          [(xforms_dir, source_extension), (classes_dir, None)], False,
                                          [(xforms_dir, source_extension), (classes_dir, None)])

        elif self.configuration['type'] == 'base':
            global_f = classes_dir + '/global%d' % id

            data_manipulation.write_base_cmllr_config(adapt_config, global_f)
            data_manipulation.write_global(global_f)

            input_transforms = [(classes_dir, None)]
            parent_transforms = []
            if parent_transform is not None:
                input_transforms.append((xforms_dir, source_extension))
                parent_transforms.append((xforms_dir, source_extension))

            htk.HERest_estimate_transform(0, adap_scp, model_adapt, xforms_dir, phones_list, adapt_mlf,
                                          num_adaptation_samples,
                                          [standard_config, adapt_config], speaker_name_width, target_extension,
                                          input_transforms, False, parent_transforms)


        else:
            raise Exception("Unknown adaptation type!")


        return (target_extension, adapt_config, speaker_name_width)

def parse_config(config_file_names):
    default_config = dict([(k,str(v)) for k,v in Model().configuration.items()])
    default_config.update(dict([(k,str(v)) for k,v in Experiment().configuration.items()]))

    config = SafeConfigParser(default_config)
    config.read(config_file_names if len(config_file_names) > 0 else "recognition_config")

    model = Model(config)
    
    experiments = {}

    for section in config.sections():
        if section.startswith('exp_'):
            experiments.update(parse_exp_config_section(config, section, model))
    return experiments


def parse_exp_config_section(config, section, model):

    experiments = []
    experiments.append(Experiment(section[4:], model))

    default_config = copy.deepcopy(experiments[0].configuration)

    for key in default_config.iterkeys():
        if ',' not in config.get(section,key):
            val = type(default_config[key])(config.get(section,key))
            if val == "":
                raise Exception("Config Exception: %s / %s not set" % (section,key))

            for experiment in experiments:
                experiment.configuration[key] = val
        else:
            vals = [type(default_config[key])(val) for val in config.get(section,key).split(',')]
            new_experiments = []
            for old_experiment in experiments:
                for val in vals:
                    experiment = Experiment( '%s_%s-%s-' %(old_experiment.name,key,val), model)
                    #experiment.configuration.update(old_experiment.configuration)
                    experiment.configuration = copy.deepcopy(old_experiment.configuration)
                    experiment.configuration[key] = val
                    new_experiments.append(experiment)

            experiments = new_experiments


    adaptation_lists = parse_adap_config(config,section)

    if len(adaptation_lists) > 0:
        if len(adaptation_lists) == 1:
            for experiment in experiments:
                experiment.adaptations = copy.deepcopy(adaptation_lists[0])
        else:
            new_experiments = []
            for old_experiment in experiments:
                for adaptation_list in adaptation_lists:
                    experiment = Experiment( '%s%s' %(old_experiment.name,''.join([adaptation.name for adaptation in adaptation_list])), model)
                    experiment.configuration = copy.deepcopy(old_experiment.configuration)
                    experiment.adaptations = copy.deepcopy(adaptation_list)
                    new_experiments.append(experiment)

            experiments = new_experiments

    for experiment in experiments:
        experiment.replace_config_vars()

    return dict([(experiment.name, experiment) for experiment in experiments])

def parse_adap_config(config,section):
    adaptation_lists = [[]]

    default_adaptation = Adaptation('')
    default_config = copy.deepcopy(default_adaptation.configuration)
    index = 1
    while(config.has_option(section,'adap%s_type'%index)):
        adaptations = []
        adaptations.append(copy.deepcopy(default_adaptation))
#        default_config = copy.deepcopy(adaptations[0].configuration)

        for base_key in default_config.iterkeys():
            key = "adap%s_%s" % (index,base_key)
            if config.has_option(section,key):
                if ',' not in config.get(section,key):
                    val = type(default_config[base_key])(config.get(section,key))
                    if val == "":
                        raise Exception("Config Exception: %s / %s not set" % (section,key))

                    for adaptation in adaptations:
                        adaptation.configuration[base_key] = val
                else:
                    vals = [type(default_config[base_key])(val) for val in config.get(section,key).split(',')]
                    new_adaptations = []
                    for old_adaptation in adaptations:
                        for val in vals:
                            adaptation = Adaptation( '%s_%s-%s-' %(old_adaptation.name,key,val))
                            adaptation.configuration = copy.deepcopy(old_adaptation.configuration)
                            adaptation.configuration[base_key] = val
                            new_adaptations.append(adaptation)

                    adaptations = new_adaptations

        if len(adaptations) == 1:
            for adaptation_list in adaptation_lists:
                adaptation_list.append(adaptations[0])
        else:
            new_adaptation_lists = []
            for adaptation_list in adaptation_lists:
                for adaptation in adaptations:
                    new_adaptation_list = copy.deepcopy(adaptation_list)
                    new_adaptation_list.append(adaptation)
                    new_adaptation_lists.append(new_adaptation_list)
            adaptation_lists = new_adaptation_lists
        index = index + 1

    return adaptation_lists

def run_experiments(experiments, tasks_per_experiment=50,total_tasks=100,max_fail_count=3):
    global pool
    pool = multiprocessing.Pool(max(total_tasks // tasks_per_experiment,1))

    runnable_experiments = [experiment for experiment in experiments.values() if (not experiment.done) and experiment.fail_count < max_fail_count and experiment.are_dependencies_ok(experiments)]
    while len(runnable_experiments) > 0:
#        results = [pool.apply_async(experiment) for experiment in runnable_experiments]
#
#        for result in results:
#            name, done = result.get(9999999)
        for name,done in [experiment() for experiment in runnable_experiments]:
            experiments[name].done = done
            if not done:
                experiments[name].fail_count = experiments[name].fail_count + 1



        runnable_experiments = [experiment for experiment in experiments.values() if (not experiment.done) and experiment.fail_count < max_fail_count and experiment.are_dependencies_ok(experiments)]

if __name__ == "__main__":
    usage = "usage: %prog [options] configfiles"
    
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-n", "--num-tasks", type="int", dest="num_tasks",help="Number of different tasks", default=50)
    parser.add_option("-s", "--step",      type="int", dest="step",      help="Starting step", default=0)
    parser.add_option("-V", "--verbosity", type="int", dest="verbosity", help="Verbosity",     default=1)
    parser.add_option("-p", "--priority", type="int", dest="priority", help="priority (more is worse)",     default=0)
    parser.add_option('-x', '--exclude-nodes', dest="exclude_nodes", help="Triton nodes to exclude", default="")
    parser.add_option('-d', '--dir', dest="recognition_dir", help="parameter used for subprocesses", default="")

    options, configs = parser.parse_args()


    if len(options.recognition_dir) == 0:
        experiments = parse_config(configs)
        for exp in experiments.keys():
            experiments[exp].launch_options = vars(options)
        run_experiments(experiments)
    else:
        experiments = parse_config([options.recognition_dir + '/config'])
        if len(experiments) != 1:
            sys.exit("Expected exactly one experiment!")

        htk.num_tasks = options.num_tasks
        htk.default_HERest_pruning = ['300.0', '500.0', '2000.0']
        job_runner.default_options["verbosity"] = 10
        
        for name,exp in experiments.items():
            print "Start running %s" % exp.name
            exp.run()
            print "Stop running %s" % exp.name
            if exp.done:
                sys.exit(0)
            else:
                sys.exit(100)


