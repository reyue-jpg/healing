# selenium_exec.py (或你的主程序)
import logging
from typing import Optional
import threading
from selenium.webdriver.common.by import By

# 从utils包初始化
from utils.logutil import get_logger
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from Property import WebElementData
from experta import *

logger = get_logger()

# 自动下载并使用兼容的ChromeDriver
driver_path = ChromeDriverManager().install()
service = ChromeService(executable_path=driver_path)
driver = Chrome(service=service)

driver.get("https://www.baidu.com")
webelement = driver.find_element(By.ID, "chat-textarea")
elementData = WebElementData.from_selenium_element(
    webelement,
    include_attributes=True,
    custom_attributes=["data-custom"]
)
print(elementData)
print(elementData.xpath)