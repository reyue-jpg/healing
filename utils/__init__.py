# 延迟导入以避免循环导入问题
__auth__ = 'FUHAO'

def get_config_handler():
    """延迟导入配置处理器"""
    from utils.configutil.configutil import IniConfigHandler
    return IniConfigHandler

def get_logger():
    """延迟导入日志记录器"""
    from utils.logutil.logutil import BuildLogger
    configparser = get_config_handler()()
    log_level = configparser.get_log_level()
    return BuildLogger(use_console=True, log_level=log_level)

# 为了向后兼容，提供这些属性
def configparser():
    return get_config_handler()()

def logger():
    return get_logger().get_logger()

__all__ = ['get_config_handler', 'get_logger', 'configparser', 'logger']