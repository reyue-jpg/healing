from selenium.webdriver.common.by import By

# 从utils包初始化
from utils import print_ascii_logo
from utils.logutil import get_logger
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from Property import WebElementData
from experta import *

logger = get_logger()

# 程序启动时打印 ASCII 艺术字
print_ascii_logo()

service = Service(executable_path=r"./selenium_driver/chromedriver.exe")
driver = Chrome(service=service)

driver.get("https://www.baidu.com/")
webelement = driver.find_element(By.ID, "kw")
elementData = WebElementData.from_selenium_element(
    webelement,
    include_attributes=True,
    custom_attributes=["data-custom"],
)
print(elementData)
print(elementData.xpath)