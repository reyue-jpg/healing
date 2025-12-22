import logging

__auth__ = 'FUHAO'

# 延迟导入，避免循环依赖
logger = None
configparser = None


def initialize():
    """延迟初始化函数，在需要时调用"""
    global logger, configparser

    from utils.logutil.logutil import BuildLogger
    from utils.cli.param import get_cli_params

    # 从命令行参数获取日志等级
    cli_params = get_cli_params()
    log_level = cli_params.log_level
    
    log_file_path = BuildLogger.get_root_dir()
    logger = BuildLogger(logdir=log_file_path, log_level=log_level, use_console=True)
    
    # configparser 设为 None，因为不再使用 IniConfigHandler
    configparser = None

    return configparser, logger

initialize()

__all__ = ['BuildLogger', 'logger', 'configparser', 'initialize']