import datetime
import os
import sys
import logging
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from typing import Optional
from pathlib import Path
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
            encoding: str = "utf-8",
            use_console: bool = False,
            use_timed_rotating: bool = False,
            timed_when: str = "midnight",
            timed_interval: int = 1,
            timed_backup_count: int = 7,
    ):

        project_root = self.get_root_dir() / 'logs'

        self.logdir = logdir or project_root
        self.log_name = log_name or 'healing_' + datetime.today().strftime('%Y%m%d') + '.log'
        # 允许传入字符串等级，做一次规范化
        if isinstance(log_level, str):
            normalized = log_level.strip().upper()
            name_to_level = getattr(logging, normalized, None)
            self.log_level = name_to_level if isinstance(name_to_level, int) else logging.DEBUG
        else:
            self.log_level = log_level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        self.logger:Optional[logging.Logger] = None

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
                '%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s', '%Y-%m-%d  %H:%M:%S'
            )

            self.logger = logging.getLogger(self.log_name)
            self.logger.setLevel(self.log_level)

            # 防止重复添加处理器
            if not self.logger.handlers:
                rotating_handler = RotatingFileHandler(
                    filename=os.path.join(self.logdir, self.log_name),
                    maxBytes=self.max_bytes,
                    encoding=self.encoding,
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
                        backupCount=kwargs['timed_backup_count'],
                        encoding=self.encoding
                    )
                    timed_handler.setFormatter(formatter)
                    timed_handler.setLevel(self.log_level)
                    self.logger.addHandler(timed_handler)
        except Exception as e:
            # 如果日志初始化失败，使用基本日志配置
            logging.basicConfig(level=self.log_level)
            self.logger = logging.getLogger(__name__)
            self.logger.error(f"日志初始化失败，使用基本配置: {e}")

    def get_root_dir(self) -> Path:
        config_names = [
            'config.ini',
            'requirements.txt',
            'settings.ini',
            'application.yaml'
        ]

        configutil_dir = Path().cwd()

        project_root = configutil_dir.parent
        search_paths = [
            project_root,
            project_root.parent,
            configutil_dir,
        ]

        unique_paths = []
        seen = set()
        for path in search_paths:
            try:
                resolved_path = path.resolve()
                if resolved_path.exists() and resolved_path not in seen:
                    seen.add(resolved_path)
                    unique_paths.append(resolved_path)
            except OSError as e:
                self.logger.error(e)
                continue

        for search_path in unique_paths:
            for file_name in config_names:
                root_marks = search_path / file_name
                if root_marks.exists():
                    return root_marks.parent

        return configutil_dir

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