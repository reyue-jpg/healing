import os
import configparser
import logging
from pathlib import Path
from util.logutil.logutil import BuildLogger
from typing import Optional, Union, List


class IniConfigError(Exception):
    """自定义配置错误类"""
    pass

class IniConfigHandler:
    """
    配置工具类，读取配置文件并完成配置初始化
    :param file_path: 配置文件路径
    :param logger 指定日志记录器，如不指定则生成一个自带的单例日志记录器
    :param env_prefix 指定需要注入环境变量的前缀
    :param env_sections 需要从配置文件中读取的配置节，默认初始化 driver
    :param overwrite_env 是否覆盖环境变量，默认为覆盖
    """

    def __init__(
            self,
            file_path: Union[str, Path] = '../../config.ini',
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
            self.logger.critical("程序因重要配置项缺失而终止")
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

                # 决定是否覆盖
                if (env_name in os.environ) or self.overwrite_env:
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

    def _cleanup_env_silent(self):
        """静默清理环境变量，不记录日志（用于 atexit 和 __del__）"""
        try:
            for env_name in list(self.injected_env_var):  # 使用列表副本避免迭代时修改
                if env_name in self.original_env_var:
                    os.environ[env_name] = self.original_env_var[env_name]
                else:
                    if env_name in os.environ:
                        del os.environ[env_name]

            self.injected_env_var.clear()
            self.original_env_var.clear()
        except Exception:
            # 忽略所有异常，确保程序正常退出
            pass

    def _check_env(self, var_set: set):
        for env_name in var_set:
            value = os.environ.get(env_name)
            self.logger.debug(f"执行环境变量注入检查:{env_name}={value}")

    def __enter__(self):
        return self

    def __exit__(self):
        self.cleanup_env()
        # 返回False代表不处理异常，让异常继续传播
        return False

    def __del__(self):
        self._cleanup_env_silent()


if __name__ == '__main__':
    config = IniConfigHandler()