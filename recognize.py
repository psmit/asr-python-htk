
from htk2.tools import htk_config
from optparse import OptionParser

usage = "usage: %prog [options] recognition_name modelname file_list dictionary language_model"
parser = OptionParser(usage=usage)
parser.add_option('-c', '--config', dest="config")
parser.add_option('--no-local', dest='local_allowed', default=True, action="store_false")
htk_config = htk_config(debug_flags=['-A','-V','-D','-T','1'])
htk_config.add_options_to_optparse(parser)

options, args = parser.parse_args()


