import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Union


class IniConfigHandler:
    """简化的配置处理器：不再从文件读取配置，而是通过参数或默认值提供配置。

    目标是移除对配置文件的依赖，同时保持原有接口的兼容性：
    - `log_level`：整数或字符串，决定日志等级
    - `found_config_path`/`file_path`：保留属性但为 `None`
    - `update_env`：从传入的 `driver_settings` 字典注入环境变量（不再从文件读取）
    - `cleanup_env`：撤销注入的环境变量
    """

    def __init__(
            self,
            logger: Optional[logging.Logger] = None,
            overwrite_env: bool = True,
            log_level: Optional[int] = logging.DEBUG,
            driver_settings: Optional[Dict[str, str]] = None,
    ):
        from utils.logutil.logutil import BuildLogger

        self.file_path = None
        self.logger = logger or BuildLogger.get_default_logger(use_console=True)
        self.overwrite_env = overwrite_env
        # 允许传入字符串等级
        if isinstance(log_level, str):
            normalized = log_level.strip().upper()
            level = getattr(logging, normalized, logging.DEBUG)
            self.log_level = level
        else:
            self.log_level = log_level

        self.original_env_var: Dict[str, str] = {}
        self.injected_env_var = set()

        # 如果提供了 driver 设置，则注入环境变量
        self.driver_settings = driver_settings

        # 立即应用日志等级
        try:
            self.logger.setLevel(self.log_level)
            for handler in list(self.logger.handlers):
                handler.setLevel(self.log_level)
        except Exception:
            pass

        # 注入环境变量（如果提供）
        try:
            self.update_env(self.driver_settings)
        except Exception:
            # 保持兼容：如果没有提供 driver 设置，跳过注入
            pass

    def update_env(self, driver_settings: Optional[Dict[str, str]] = None) -> None:
        """从字典注入驱动相关环境变量（例如 {'chrome': 'C:/path/chromedriver.exe'})。

        如果 `driver_settings` 为 None，则不做任何事情。
        """
        if not driver_settings:
            return

        for key, value in driver_settings.items():
            env_name = f"{self.env_prefix}{key.upper()}"
            if env_name in os.environ:
                self.original_env_var[env_name] = os.environ[env_name]

            if (env_name in os.environ) and (not self.overwrite_env):
                self.logger.debug(f"保留已存在环境变量: {env_name}")
                continue

            os.environ[env_name] = value
            self.injected_env_var.add(env_name)
            self.logger.debug(f"环境变量已注入: {env_name}={value}")

    def cleanup_env(self) -> None:
        """恢复原始环境变量并清理注入的变量。"""
        try:
            for env_name in list(self.injected_env_var):
                try:
                    if env_name in self.original_env_var:
                        os.environ[env_name] = self.original_env_var[env_name]
                        self.logger.info(f"恢复原始环境变量 {env_name}={self.original_env_var[env_name]}")
                    else:
                        if env_name in os.environ:
                            del os.environ[env_name]
                        self.logger.info(f"移除注入环境变量 {env_name}")
                except Exception as e:
                    self.logger.error(f"清理环境变量 {env_name} 时出错: {e}")

            self.injected_env_var.clear()
            self.original_env_var.clear()
        except Exception as e:
            try:
                print(f"清理环境变量过程中发生错误: {e}")
            except Exception:
                pass

    def get_file_path(self):
        return self.file_path

    def get_log_level(self) -> Optional[int]:
        return self.log_level

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup_env()
        return False