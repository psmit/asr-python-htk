#!/usr/bin/env python2.6
from ConfigParser import SafeConfigParser
import multiprocessing
import copy
import random

class Model:
    configuration = {
        'model_dir': '',
        'lm': '',
        'lm_rescore': None,
        'config': '',
        'speaker_name_width': 5,
        'recognize_scp': '|MODEL|/files/eval.scp',
        'recognize_mlf': '|MODEL|/files/words.mlf',
        'ref_del_char': None,
        'word_suffix': None,
    }

    def __init__(self,config=None):
        if config is not None:
            for key in self.configuration.iterkeys():
                if self.configuration[key] is not None:
                    t = type(self.configuration[key]) if self.configuration[key] is not None else str
                    self.configuration[key] =t(config.get('model',key))
                if self.configuration[key] == "":
                    raise Exception("Config Exception: [model] / %s not set" % key)

class Experiment:
    configuration = {
        'model_name': 'hmm_si',
        'lm_scale': 19,
        'beam': 250,
        'end_beam': -1,
        'num_tokens': 32,
    }

    dependencies = None
    adaptations = None

    done = False
    name = "exp"
    fail_count = 0


    def __init__(self, name='exp', model=None):
        self.name=name
        self.model=model


    def run(self):
        self.done = (random.random() < 1.0)
        print "Do Experiment %s, success %s" % (self.name, self.done)

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
                            adaptation.configuration[key] = adaptation.configuration[key].replace('|EXP_%s|' % dependency, dependency)
        return

    def are_dependencies_ok(self, experiments):
        for dependency in self.dependencies:
            if not experiments[dependency].done:
                return False
        return True

    def __call__(self):
        self.run()
        return (self.name,self.done)
        
   
class Adaptation:
    configuration = {
        'type': 'base',
        'scp': '',
        'mlf': '',
        'nodes': 128,
        'occupation': 1000,
        'num_sentences': 'all',
    }

    name = 'adaptation'
    def __init__(self, name='adaptation'):
        self.name=name

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
                    experiment = Experiment( '%s_%s(%s)' %(old_experiment.name,key,val), model)
                    experiment.configuration.update(old_experiment.configuration)
                    experiment.configuration[key] = val
                    new_experiments.append(experiment)

            experiments = new_experiments


    adaptation_lists = parse_adap_config(config,section)

    if len(adaptation_lists) > 0:
        if len(adaptation_lists) == 1:
            for experiment in experiments:
                experiment.adaptations = adaptation_lists[0]
        else:
            new_experiments = []
            for old_experiment in experiments:
                for adaptation_list in adaptation_lists:
                    experiment = Experiment( '%s%s' %(old_experiment.name,''.join([adaptation.name for adaptation in adaptation_list])), model)
                    experiment.configuration = copy.deepcopy(old_experiment.configuration)
                    experiment.adaptations = adaptation_list
                    new_experiments.append(experiment)

            experiments = new_experiments
            
    for experiment in experiments:
        experiment.replace_config_vars()

    return dict([(experiment.name, experiment) for experiment in experiments])

def parse_adap_config(config,section):
    adaptation_lists = [[]]

    index = 1
    while(config.has_option(section,'adap%s_type'%index)):
        adaptations = []
        adaptations.append(Adaptation(''))
        default_config = copy.deepcopy(adaptations[0].configuration)

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
                            adaptation = Adaptation( '%s_%s(%s)' %(old_adaptation.name,key,val))
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

def run_experiments(experiments,tasks_per_experiment=50,total_tasks=800,max_fail_count=3):
    pool = multiprocessing.Pool(max(total_tasks // tasks_per_experiment,1))

    runnable_experiments = [experiment for experiment in experiments.values() if (not experiment.done) and experiment.fail_count < max_fail_count and experiment.are_dependencies_ok(experiments)]
    while len(runnable_experiments) > 0:
        results = [pool.apply_async(experiment) for experiment in runnable_experiments]

        for result in results:
            name, done = result.get()
            experiments[name].done = done
            if not done:
                experiments[name].fail_count = experiments[name].fail_count +1

        print "Bla"
        runnable_experiments = [experiment for experiment in experiments.values() if (not experiment.done) and experiment.fail_count < max_fail_count and experiment.are_dependencies_ok(experiments)]

if __name__ == "__main__":
    experiments = parse_config([])
    run_experiments(experiments)