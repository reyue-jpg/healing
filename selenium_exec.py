import os

from tensorflow.python.data.ops.optional_ops import Optional

from util.logutil import logutil
from selenium import webdriver
from selenium.webdriver.chrome import webdriver
from selenium.webdriver.support.wait import WebDriverWait

CUR_DIR = os.path.split(os.path.realpath(__file__))[0]
logger = logutil.initlogger(os.path.join(CUR_DIR, "logs"))

class SeleniumDriver:
    def __init__(self):
        self.driver = None

    def get_driver(self, driver_name: str, url: str):
        if driver_name == 'Chrome' or driver_name == 'chrome' or driver_name == 'C' or driver_name == 'c':
            self.driver = webdriver.Chrome()
            logger.info('Chrome 浏览器初始化')
        elif driver_name == 'Firefox' or driver_name == 'firefox' or driver_name == 'F' or driver_name == 'f':
            self.driver = webdriver.Firefox()
            logger.info('Firefox 浏览器初始化')
        elif driver_name == 'Edge' or driver_name == 'edge' or driver_name == 'E' or driver_name == 'e':
            self.driver = webdriver.Edge()
            logger.info('Edge 浏览器初始化')
        else:
            logger.error("仅支持 Chrome | Firefox | Edge 浏览器")

        self.driver.get(url)



    