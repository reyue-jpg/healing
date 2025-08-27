import os
import configparser
import logging
from pathlib import Path
from util.logutil.logutil import BuildLogger
from typing import Optional, Union, List


class IniConfigError(Exception):
    pass

class IniConfigHandler:

    def __init__(
            self,
            file_path: Union[str, Path] = './',
            logger: Optional[logging.Logger] = None,
            env_prefix: Optional[str] = 'APP_',
            env_sections: List[str]=['driver'],
            overwrite_env: bool = True
    ):

        self.file_path =  Path(file_path).resolve()
        self.logger = logger or BuildLogger.get_default_logger(use_console=True)
        self.env_prefix = env_prefix
        self.env_sections = env_sections
        self.overwrite_env = overwrite_env
        self.original_env_var = {}
        self.injected_env_var = set()

        if not self.file_path.exists():
            error_msg = f"配置文件不存在: {self.file_path}"
            self.logger.critical("程序因重要配置项确实而终止")
            raise FileNotFoundError(error_msg)

        self.parser = configparser.ConfigParser()
        self.parser.optionxform = str

        try:
            self.parser.read(self.file_path, encoding="utf-8")
            self.logger.info(f"读取配置 {self.file_path}")
        except configparser.Error as e:
            raise IniConfigError(f"解析配置文件失败 {e}")

        self.update_env()

    def update_env(self) -> None:
        for section in self.env_sections:
            if not self.parser.has_section(section):
                self.logger.error(f"配置节不存在，跳过环境变量注入: [{section}]")
                continue

            for key in self.parser.options(section):
                env_name = f"{self.env_prefix}{key.upper()}"

                if env_name in os.environ:
                    self.original_env_var[env_name] = os.environ[env_name]

                if not os.environ[env_name] or self.overwrite_env:
                    value = self.parser.get(section, key)
                    os.environ[env_name] = value
                    self.injected_env_var.add(env_name)
                    self.logger.debug(f"环境变量已注入: {env_name}={value}")
                else:
                    self.logger.warning(f"跳过本次环境变量注入")

        self._check_env(self.injected_env_var)

    def cleanup_env(self):
        for env_name in self.injected_env_var:
            if env_name in self.original_env_var:
                os.environ[env_name] = self.original_env_var[env_name]
                self.logger.info(f"恢复原始环境变量 {env_name}={self.original_env_var[env_name]}")
            else:
                del os.environ[env_name]
                self.logger.warning(f"清理环境变量 {env_name}")

        self.injected_env_var.clear()
        self.original_env_var.clear()
        self.logger.info("所有注入的环境变量已清理...")

    def _check_env(self, var_set: set):
        for subset in var_set:
            subset = os.environ.get(subset)
            self.logger.debug(f"执行环境变量注入检查:{subset}")

    def __enter__(self):
        return self

    def __exit__(self):
        self.cleanup_env()
        # 返回False代表不处理异常，让异常继续传播
        return False

    def __del__(self):
        try:
            self.cleanup_env()
        except Exception as e:
            pass