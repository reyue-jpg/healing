import logging
import os
import utils
from typing import Optional
# from utils.logutil.logutil import BuildLogger
# from utils.configutil.configutil import IniConfigHandler
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait


class SeleniumDriver:
    """
    :param
        pass

    :return
        pass
    """
    def __init__(self, logger: Optional[logging.Logger]=None):
        self.driver = None
        self.logger = logger


    def get_driver(self, driver_name: str, url: str):
        if driver_name == 'Chrome' or driver_name == 'chrome' or driver_name == 'C' or driver_name == 'c':
            self.driver = webdriver.Chrome()
            self.logger.info('Chrome 浏览器初始化')
        elif driver_name == 'Firefox' or driver_name == 'firefox' or driver_name == 'F' or driver_name == 'f':
            self.driver = webdriver.Firefox()
            self.logger.info('Firefox 浏览器初始化')
        elif driver_name == 'Edge' or driver_name == 'edge' or driver_name == 'E' or driver_name == 'e':
            self.driver = webdriver.Edge()
            self.logger.info('Edge 浏览器初始化')
        else:
            self.logger.error("仅支持 Chrome | Firefox | Edge 浏览器")
            raise ValueError("不支持的浏览器")

        self.driver.get(url)

if __name__ == '__main__':
    driver = SeleniumDriver()
    driver.get_driver("c", "https://www.baidu.com")