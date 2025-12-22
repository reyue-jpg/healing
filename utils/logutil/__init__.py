from .logutil import BuildLogger

__all__ = ['get_logger']

def get_logger():
    logger = BuildLogger(use_console=True)
    return logger.get_logger()