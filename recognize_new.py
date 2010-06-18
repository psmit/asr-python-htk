#!/usr/bin/env python2.6
from ConfigParser import SafeConfigParser


class Model:
    model_dir = ''
    lm = ''
    lm_rescore = None
    lm_scale = 19
    config = ''
    speaker_width = 5

    recognize_scp = None
    recognize_mlf = None
    ref_del_char = None
    word_suffix = None

class Experiment:
    done = False
    name = "exp"
    model_name = 'hmm_si'
    model = None
    beam = 250
    end_beam = -1
    num_tokes = 32

    dependencies = []

    def run(self):
        success = True
        return success

    def are_dependencies_ok(self, experiments):
        for dependency in self.dependencies:
            if not experiments[dependency].done:
                return False
        return True
        
   
class Adaptation:
    type = 'base'
    scp = ''
    mlf = ''
    nodes = 128
    occupation = 1000
    num_sentences = 'all'

def parse_config(config_file_names):
    config = SafeConfigParser({})
    config.read(config_file_names if len(config_file_names) > 0 else "recognition_config")

    model = parse_model(config)
    experiments = {}

    for section in config.sections():
        if section.startswith('exp_'):
            experiments.update(parse_exp_config_section(config, section))
    return model,experiments

def parse_model(config):
    model = Model()

    return model

def parse_exp_config_section(config, section, model):

    return []

def run_experiments(model,experiments,tasks_per_experiment=50,total_tasks=800):
    pass

if __name__ == "__main__":
    pass