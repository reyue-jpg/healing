import logging

__auth__ = 'FUHAO'

# 延迟导入，避免循环依赖
logger = None
configparser = None


def initialize():
    """延迟初始化函数，在需要时调用"""
    global logger, configparser

    from utils.configutil.configutil import IniConfigHandler
    from utils.logutil.logutil import BuildLogger

    configparser = IniConfigHandler()
    log_level = configparser.get_log_level()
    log_file_path = configparser.found_config_path
    logger = BuildLogger(logdir=log_file_path, log_level=log_level, use_console=True)

    return configparser, logger

initialize()

__all__ = ['IniConfigHandler', 'BuildLogger', 'logger', 'configparser', 'initialize']