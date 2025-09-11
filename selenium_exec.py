import logging
import os
from typing import Optional
from utils.logutil.logutil import BuildLogger
from utils.configutil.configutil import IniConfigHandler
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService


class SeleniumDriver:
    """
    Selenium 浏览器驱动管理类

    :param logger: 可选的日志记录器实例
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.driver = None
        self.logger = logger or BuildLogger(use_console=True).get_logger()

    def get_driver(self, driver_name: str, url: str):
        """
        获取并初始化浏览器驱动

        :param driver_name: 浏览器名称 (chrome/firefox/edge 或其首字母)
        :param url: 要访问的URL
        :return: 初始化后的浏览器驱动实例
        """
        driver_name = driver_name.lower()

        if driver_name in ['chrome', 'c']:
            # 从环境变量获取 ChromeDriver 路径
            chrome_driver_path = os.environ.get('APP_CHROME')
            if not chrome_driver_path:
                self.logger.error("未找到 ChromeDriver 路径环境变量 (APP_CHROME)")
                raise ValueError("ChromeDriver 路径未配置")

            # 创建 Chrome 选项
            chrome_options = webdriver.ChromeOptions()
            # 添加常用选项
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--start-maximized')

            # 创建服务并指定驱动程序路径
            service = ChromeService(executable_path=chrome_driver_path)

            # 初始化驱动
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.logger.info(f'Chrome 浏览器初始化，使用驱动: {chrome_driver_path}')

        elif driver_name in ['firefox', 'f']:
            # 从环境变量获取 GeckoDriver 路径
            firefox_driver_path = os.environ.get('APP_FIREFOX')
            if not firefox_driver_path:
                self.logger.error("未找到 GeckoDriver 路径环境变量 (APP_FIREFOX)")
                raise ValueError("GeckoDriver 路径未配置")

            # 创建 Firefox 选项
            firefox_options = webdriver.FirefoxOptions()
            # 添加常用选项
            firefox_options.add_argument('--start-maximized')

            # 创建服务并指定驱动程序路径
            service = FirefoxService(executable_path=firefox_driver_path)

            # 初始化驱动
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            self.logger.info(f'Firefox 浏览器初始化，使用驱动: {firefox_driver_path}')

        elif driver_name in ['edge', 'e']:
            # 从环境变量获取 EdgeDriver 路径
            edge_driver_path = os.environ.get('APP_EDGE')
            if not edge_driver_path:
                self.logger.error("未找到 EdgeDriver 路径环境变量 (APP_EDGE)")
                raise ValueError("EdgeDriver 路径未配置")

            # 创建 Edge 选项
            edge_options = webdriver.EdgeOptions()
            # 添加常用选项
            edge_options.add_argument('--no-sandbox')
            edge_options.add_argument('--disable-dev-shm-usage')
            edge_options.add_argument('--disable-gpu')
            edge_options.add_argument('--start-maximized')

            # 创建服务并指定驱动程序路径
            service = EdgeService(executable_path=edge_driver_path)

            # 初始化驱动
            self.driver = webdriver.Edge(service=service, options=edge_options)
            self.logger.info(f'Edge 浏览器初始化，使用驱动: {edge_driver_path}')

        else:
            self.logger.error("仅支持 Chrome | Firefox | Edge 浏览器")
            raise ValueError("不支持的浏览器")

        # 导航到指定URL
        self.driver.get(url)

        # 返回驱动实例，方便链式调用
        return self.driver

    def quit_driver(self):
        """关闭浏览器驱动"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logger.info("浏览器已关闭")

if __name__ == '__main__':
    handler = IniConfigHandler()
    try:
        driver = SeleniumDriver()
        driver.get_driver("e", "https://www.baidu.com")
    finally:
        handler.cleanup_env()