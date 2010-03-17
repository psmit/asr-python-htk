
import logging;

logger = None

def create_logger(name, file):
    global logger
    
    logger = logging.getLogger(name)
    
    logger.setLevel(logging.DEBUG)
    
    # create console handler and set level to info
    sh_ch = logging.StreamHandler()
    sh_ch.setLevel(logging.INFO)
    sh_formatter = logging.Formatter("%(asctime)s - %(message)s")
    sh_ch.setFormatter(sh_formatter)
    logger.addHandler(sh_ch)
    
    # create console handler and set level to info
    f_ch = logging.FileHandler(file)
    f_ch.setLevel(logging.DEBUG)
    f_formatter = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
    f_ch.setFormatter(f_formatter)
    logger.addHandler(f_ch)
