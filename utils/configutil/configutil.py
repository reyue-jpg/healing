import logging
import configparser
import os
import sys

import selenium
from selenium import webdriver
import selenium.webdriver.chrome.options
from pathlib import Path
from typing import Dict, List, Optional, Union, Iterable, Iterator

class IniConfigError(Exception):
    """自定义配置错误类"""
    pass

class IniConfigHandler:
    """
    配置工具类，读取配置文件并完成配置初始化

    :argument
        file_path: 配置文件路径
        logger 指定日志记录器，如不指定则生成一个自带的单例日志记录器
        env_prefix 指定需要注入环境变量的前缀
        env_sections 需要从配置文件中读取的配置节，默认初始化 driver
        overwrite_env 是否覆盖环境变量，默认为覆盖
        log_level 将会记录在日志中的日志等级
        original_env_var 原始环境变量，用于恢复环境时对比
        injected_env_var 一个 set 结构，保存已经注入的环境变量
        found_config_path 用于搜索可能的配置文件路径

    :return

    """

    def __init__(
            self,
            file_path: Union[str, Path] = './config.ini',
            logger: Optional[logging.Logger] = None,
            env_prefix: Optional[str] = 'APP_',
            env_sections: List[str]=['driver', 'log'],
            overwrite_env: bool = True,
            log_level:Optional[int] = logging.DEBUG
    ):

        from utils.logutil.logutil import BuildLogger
        self.file_path =  Path(file_path).resolve()
        self.logger = logger or BuildLogger.get_default_logger(use_console=True)
        self.env_prefix = env_prefix
        self.env_sections = env_sections
        self.overwrite_env = overwrite_env
        self.log_level = log_level
        self.original_env_var = {}
        self.injected_env_var = set()
        self.found_config_path:Optional[Path] = None

        if not self.file_path.exists() or self.file_path.name != 'config.ini':
            self.found_config_path = self._search_config_file()
            if self.found_config_path is None:
                error_msg = f"配置文件不存在: {self.file_path}"
                self.logger.critical("程序因重要配置项确实而终止")
                raise FileNotFoundError(error_msg)
            self.file_path = self.found_config_path

        self.parser = configparser.ConfigParser()
        self.parser.optionxform = str

        try:
            self.parser.read(self.file_path, encoding="utf-8")
            self.logger.info(f"读取配置 {self.file_path}")
        except configparser.Error as e:
            raise IniConfigError(f"解析配置文件失败 {e}")

        # 读取日志等级并立即下发到 logger 与 handlers，避免后续 DEBUG 被输出
        try:
            configured_level = self.get_log_level()
            if isinstance(configured_level, int):
                self.log_level = configured_level
                self.logger.setLevel(self.log_level)
                for handler in list(self.logger.handlers):
                    handler.setLevel(self.log_level)
        except Exception:
            # 若解析失败，保持临时 INFO 级别继续
            pass

        self.update_env()

    def update_env(self) -> None:
        for section in self.env_sections:
            # 如果不是 驱动 配置节则跳过
            if section != 'driver':
                continue
            if not self.parser.has_section(section):
                self.logger.warning(f"配置节不存在，跳过环境变量注入: [{section}]")
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

    def cleanup_env(self) -> None:
        try:
            for env_name in list(self.injected_env_var):  # 使用list创建副本，避免在迭代时修改集合
                try:
                    if env_name in self.original_env_var:
                        os.environ[env_name] = self.original_env_var[env_name]
                        self.logger.info(f"恢复原始环境变量 {env_name}={self.original_env_var[env_name]}")
                    else:
                        if env_name in os.environ:
                            del os.environ[env_name]
                        self.logger.warning(f"清理环境变量 {env_name}")
                except Exception as e:
                    self.logger.error(f"清理环境变量 {env_name} 时出错: {e}")
                    # 继续清理其他变量

            self.injected_env_var.clear()
            self.original_env_var.clear()
            self.logger.info("所有注入的环境变量已清理...")
        except Exception as e:
            # 如果日志系统不可用，尝试简单打印
            try:
                print(f"清理环境变量过程中发生错误: {e}")
            except:
                pass

    def _check_env(self, var_set: set) -> None:
        for subset in var_set:
            subset = os.environ.get(subset)
            self.logger.debug(f"执行环境变量检查: {subset}")

    def _search_config_file(self) -> Optional[Path]:
        config_names = [
            self.file_path.name,
            'config.ini',
            'settings.ini',
            'application.ini'
        ]

        configutil_dir =  Path().cwd()

        project_root = configutil_dir.parent
        search_paths = [
            project_root,
            configutil_dir,
            project_root / 'config',
            Path().home() / '.config'
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
                config_file = search_path / file_name
                self.logger.debug(f'正在搜索目录 {search_path}')
                if config_file.is_file():
                    self.logger.info(f"找到配置文件 {config_file}")
                    return config_file

        self.logger.error("未找到配置文件")
        return None

    def get_file_path(self):
        """返回实际使用的配置文件路径"""
        return self.file_path

    def get_found_config_file(self):
        """返回搜索返回的配置文件路径 (如果有)"""
        return self.found_config_path

    def get_log_level(self) -> Optional[int]:
        """返回配置文件中的日志等级（整型），默认为 logging.DEBUG"""
        level_map = {
            'CRITICAL': logging.CRITICAL,
            'FATAL': logging.FATAL,
            'ERROR': logging.ERROR,
            'WARNING': logging.WARNING,
            'WARN': logging.WARNING,
            'INFO': logging.INFO,
            'DEBUG': logging.DEBUG,
            'NOTSET': logging.NOTSET
        }

        section = 'log'
        if not self.parser.has_section(section):
            self.logger.warning(f"配置节不存在，获取日志等级失败: [{section}]，使用默认等级 DEBUG")
            return self.log_level

        # 兼容不同键名
        candidate_keys = ['LEVEL', 'Level', 'level', 'LOG_LEVEL', 'log_level']
        level_value: Optional[str] = None
        for key in candidate_keys:
            if self.parser.has_option(section, key):
                level_value = self.parser.get(section, key)
                break

        # 若找不到已知键名，则尝试读取该节中的第一个键的值
        if level_value is None:
            options = self.parser.options(section)
            if options:
                level_value = self.parser.get(section, options[0])

        if isinstance(level_value, str):
            normalized = level_value.strip().upper()
            if normalized in level_map:
                self.log_level = level_map[normalized]
            else:
                self.logger.warning(f"未知日志等级值: {level_value}，使用默认等级 DEBUG")
        return self.log_level


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_env()
        # 返回False代表不处理异常，让异常继续传播
        return False

    # def __del__(self):
    #     try:
    #         # 检查日志记录器是否仍然可用
    #         if hasattr(self, 'logger') and self.logger:
    #             self.cleanup_env()
    #     except Exception as e:
    #         # 在程序退出时，日志系统可能已经不可用，所以忽略错误
    #         try:
    #             print(f"清理环境变量时发生错误（可忽略）: {e}")
    #         except:
    #             # 如果连打印都不可用，则完全忽略
    #             pass
