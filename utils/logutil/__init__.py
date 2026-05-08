import logging
from typing import Optional, Union

from .logutil import BuildLogger

__all__ = ['get_logger', 'BuildLogger']


def get_logger(
    name: Optional[str] = None,
    level: Union[int, str] = logging.DEBUG,
    use_console: bool = False,
    **kwargs
) -> logging.Logger:
    """获取日志记录器。

    Args:
        name: 日志文件名（不含扩展名），默认为 healing_YYYYMMDD.log
        level: 日志级别，支持 int 或字符串
        use_console: 是否同时输出到控制台
        **kwargs: 传递给 BuildLogger 的其他参数
    """
    logger = BuildLogger(
        log_name=f"{name}.log" if name else None,
        log_level=level,
        use_console=use_console,
        **kwargs
    )
    return logger.get_logger()
