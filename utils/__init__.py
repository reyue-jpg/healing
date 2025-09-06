from utils.configutil.configutil import IniConfigHandler
from utils.logutil.logutil import BuildLogger

__auth__ = 'FUHAO'

configparser =IniConfigHandler()
log_level = configparser.get_log_level()
logger = BuildLogger(use_console=True, log_level=log_level)

__all__ = ['IniConfigHandler', 'BuildLogger', 'configutil', 'logger']