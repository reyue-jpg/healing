import logging
import os
import shutil
import time
import winreg
import subprocess
import requests
from typing import Optional
from utils.logutil.logutil import BuildLogger
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService

from webdriver_manager.microsoft import EdgeChromiumDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager

# 兼容性检查旧实现已下线，当前保留自动下载驱动主流程。


class SeleniumDriver:
    """
    Selenium 浏览器驱动管理类

    :param logger: 可选的日志记录器实例
    """

    def __init__(self, logger: Optional[logging.Logger]=None):
        self.driver = None
        self.logger = logger or BuildLogger(use_console=True).get_logger()

    def get_driver(self, driver_name: str, url: str, auto_download=True, force_check=True):
        """
        获取并初始化浏览器驱动

        :param driver_name: 浏览器名称 (chrome/firefox/edge 或其首字母)
        :param url: 要访问的URL
        :param auto_download: 是否自动下载兼容的驱动
        :param force_check: 是否强制检查实际驱动文件版本（已停用，保留参数以保持兼容性）
        :return: 初始化后的浏览器驱动实例
        """
        driver_name = driver_name.lower()

        # 直接使用自动下载方式获取驱动，不再从环境变量读取
        if auto_download:
            return self._get_driver_with_auto_download(driver_name, url)
        else:
            # 即使关闭自动下载，也仍按统一驱动获取流程执行
            return self._get_driver_with_auto_download(driver_name, url)

    def _try_existing_driver(self, driver_name: str, url: str):
        """尝试使用现有驱动（已停用，改用自动下载方式）"""
        # 此方法已停用，改用自动下载方式
        return self._get_driver_with_auto_download(driver_name, url)

    def _get_driver_with_auto_download(self, driver_name: str, url: str):
        """使用自动下载的兼容驱动"""
        try:
            if driver_name in ['chrome', 'c']:
                driver_path = ChromeDriverManager().install()
                service = ChromeService(executable_path=driver_path)
                chrome_options = self._get_chrome_options()
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.logger.info(f'Chrome 浏览器初始化，使用自动下载驱动: {driver_path}')

            elif driver_name in ['firefox', 'f']:
                driver_path = GeckoDriverManager().install()
                service = FirefoxService(executable_path=driver_path)
                firefox_options = self._get_firefox_options()
                self.driver = webdriver.Firefox(service=service, options=firefox_options)
                self.logger.info(f'Firefox 浏览器初始化，使用自动下载驱动: {driver_path}')

            elif driver_name in ['edge', 'e']:
                # 尝试下载最新稳定版
                try:
                    driver_path = EdgeChromiumDriverManager().install()
                except Exception as e:
                    self.logger.warning(f"下载最新Edge驱动失败: {e}")
                    raise

                service = EdgeService(executable_path=driver_path)
                edge_options = self._get_edge_options()
                self.driver = webdriver.Edge(service=service, options=edge_options)
                self.logger.info(f'Edge 浏览器初始化，使用自动下载驱动: {driver_path}')

            # 打开指定网址
            self.driver.get(url)
            return self.driver

        except Exception as e:
            self.logger.error(f"自动下载驱动失败: {e}")
            self.logger.error("建议手动下载对应版本的驱动")
            if driver_name in ['chrome', 'c']:
                self.logger.error("Chrome驱动下载地址: https://chromedriver.chromium.org/")
            elif driver_name in ['edge', 'e']:
                self.logger.error(
                    "Edge驱动下载地址: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
            raise



    def _setup_chrome_driver(self, url: str):
        """设置Chrome驱动（已停用，改用自动下载方式）"""
        # 此方法已停用，改用自动下载方式
        return self._get_driver_with_auto_download('chrome', url)

    def _setup_firefox_driver(self, url: str):
        """设置Firefox驱动（已停用，改用自动下载方式）"""
        # 此方法已停用，改用自动下载方式
        return self._get_driver_with_auto_download('firefox', url)

    def _setup_edge_driver(self, url: str):
        """设置Edge驱动（已停用，改用自动下载方式）"""
        # 此方法已停用，改用自动下载方式
        return self._get_driver_with_auto_download('edge', url)

    def _get_chrome_options(self):
        """获取Chrome浏览器选项"""
        chrome_options = webdriver.ChromeOptions()
        # 添加常用选项
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--start-maximized')
        # 移除自动化控制特征
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        return chrome_options

    def _get_firefox_options(self):
        """获取Firefox浏览器选项"""
        firefox_options = webdriver.FirefoxOptions()
        # 添加常用选项
        firefox_options.add_argument('--start-maximized')
        return firefox_options

    def _get_edge_options(self):
        """获取Edge浏览器选项"""
        edge_options = webdriver.EdgeOptions()
        # 添加常用选项
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-gpu')
        edge_options.add_argument('--start-maximized')
        # 移除自动化控制特征
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        return edge_options

    def quit_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("浏览器已关闭")


if __name__ == '__main__':
    try:
        driver = SeleniumDriver()
        # 使用自动下载方式获取驱动
        driver.get_driver("c", "https://www.baidu.com", auto_download=True, force_check=True)
    except Exception as e:
        print(f"驱动初始化失败: {e}")