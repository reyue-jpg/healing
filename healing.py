from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium_interceptor import SeleniumInterceptor

# 正常初始化 driver，这一步和之前完全一样
service = Service(executable_path=r"./selenium_driver/chromedriver.exe")
driver = Chrome(service=service)

# 用 with 块激活拦截器，with 块内的所有操作都会被自动拦截
with SeleniumInterceptor(driver) as d:
    d.get("https://www.baidu.com/")

    # find_element 和之前写法完全一致，无需任何改动
    # 内部自动完成：创建 WebElementData 快照 → 写入全局注册表
    search_box = d.find_element(By.ID, "kw")

    # click、send_keys 等操作也和之前完全一致
    # 内部自动完成：拦截操作 → 记录事件 → 异常时触发自愈
    search_box.send_keys("hello")
    search_box.clear()

    btn = d.find_element(By.ID, "su")
    btn.click()

# with 块结束后，driver 自动还原为原始状态，可继续正常使用
driver.quit()