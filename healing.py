# selenium_exec.py (或你的主程序)
import logging
from typing import Optional

# 从utils包初始化
from utils import initialize
from selenium_exec import  SeleniumDriver

# 初始化配置和日志
configparser, logger = initialize()

driver = SeleniumDriver()
driver.get_driver("c", "https://www.baidu.com")