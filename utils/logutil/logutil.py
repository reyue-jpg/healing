import datetime
import os
import sys
import logging
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
from Property import WebElementData
# from utils.configutil.configutil import IniConfigHandler

class BuildLogger:
    _instance = {}
    _lock = threading.Lock()

    def __init__(
            self,
            logdir: Optional[str] = None,
            log_name: Optional[str] = None,
            log_level: int = logging.DEBUG,
            max_bytes: int = 10 * 1024 * 1024,
            backup_count: int = 3,
            use_console: bool = False,
            use_timed_rotating: bool = False,
            timed_when: str = "midnight",
            timed_interval: int = 1,
            timed_backup_count: int = 7,
    ):

        self.logdir = logdir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        self.log_name = log_name or datetime.today().strftime('%Y%m%d') + '.log'
        # 允许传入字符串等级，做一次规范化
        if isinstance(log_level, str):
            normalized = log_level.strip().upper()
            name_to_level = getattr(logging, normalized, None)
            self.log_level = name_to_level if isinstance(name_to_level, int) else logging.DEBUG
        else:
            self.log_level = log_level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.logger = None

        self._ensure_log_directory()
        self._init_logger(
            use_console=use_console,
            use_timed_rotating=use_timed_rotating,
            timed_when=timed_when,
            timed_interval=timed_interval,
            timed_back_count=timed_backup_count
        )

    def _init_logger(self, **kwargs):
        try:
            formatter = logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
            )

            self.logger = logging.getLogger(self.log_name)
            self.logger.setLevel(self.log_level)

            # 防止重复添加处理器
            if not self.logger.handlers:
                rotating_handler = RotatingFileHandler(
                    filename=os.path.join(self.logdir, self.log_name),
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count
                )
                rotating_handler.setFormatter(formatter)
                rotating_handler.setLevel(self.log_level)
                self.logger.addHandler(rotating_handler)

                if kwargs.get('use_console'):
                    console_handler = logging.StreamHandler(sys.stdout)
                    console_handler.setFormatter(formatter)
                    console_handler.setLevel(self.log_level)
                    self.logger.addHandler(console_handler)

                if kwargs.get('use_timed_rotating'):
                    timed_handler = TimedRotatingFileHandler(
                        filename=os.path.join(self.logdir, self.log_name),
                        when=kwargs['timed_when'],
                        interval=kwargs['timed_interval'],
                        backupCount=kwargs['timed_backup_count']
                    )
                    timed_handler.setFormatter(formatter)
                    timed_handler.setLevel(self.log_level)
                    self.logger.addHandler(timed_handler)
        except Exception as e:
            # 如果日志初始化失败，使用基本日志配置
            logging.basicConfig(level=self.log_level)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"日志初始化失败，使用基本配置: {e}")

    def _ensure_log_directory(self):
        os.makedirs(self.logdir, exist_ok=True)

    def add_custom_handler(self, handler):
        if not isinstance(handler, logging.Handler):
            raise TypeError("The handler must be a subclass of logging.Handler")
        self.logger.addHandler(handler)

    def get_logger(self) -> logging.Logger:
        return self.logger

    @classmethod
    def get_default_logger(cls, **kwargs) -> logging.Logger:
        instance_key = str(kwargs)

        with cls._lock:
            if instance_key not in cls._instance:
                cls._instance[instance_key] = cls(**kwargs)

            return cls._instance[instance_key].logger