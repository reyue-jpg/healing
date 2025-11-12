# selenium_exec.py (或你的主程序)
import logging
from typing import Optional
import threading

# 从utils包初始化
from utils import logger, configparser
from selenium_exec import  SeleniumDriver



driver = SeleniumDriver()
driver.get_driver("c", "https://www.baidu.com")
