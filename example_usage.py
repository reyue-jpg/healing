"""
示例：演示拦截器的完整用法。

运行前请确保浏览器驱动在系统可访问位置。
"""
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from headling.interceptor.selenium_interceptor import SeleniumInterceptor
from headling.registry.element_registry import ElementRegistry
from headling.runtime.monitor import Monitor


def main():
    # ── 1. 正常初始化浏览器驱动（与之前一致）──
    service = Service(executable_path=r"./selenium_driver/chromedriver.exe")
    driver = Chrome(service=service)

    # ── 2. 可选：创建监控器（自愈引擎暂时为空）──
    monitor = Monitor()

    # ── 3. 使用上下文管理器激活拦截器 ──
    #    在上下文代码块内，查找元素方法会被全局替换
    #    在上下文结束后会自动还原原始行为
    with SeleniumInterceptor(driver, monitor=monitor) as d:
        d.get("https://www.baidu.com/")

        # 元素查找会被拦截：
        #   - 成功后自动创建元素快照
        #   - 快照写入全局注册表（键值为定位器）
        #   - 返回包装元素对象（接口与原生元素一致）
        search_box = d.find_element(By.ID, "kw")

        # 元素操作同样会被拦截：
        #   - 记录到监控器
        #   - 遇到陈旧元素异常时会尝试从注册表取快照自愈
        search_box.send_keys("Selenium 自愈测试")

        btn = d.find_element(By.ID, "su")
        btn.click()

    # ── 4. 上下文退出后，元素查找方法已还原，可继续正常使用 ──
    driver.quit()

    # ── 5. 查看注册表中缓存的元素快照 ──
    registry = ElementRegistry.get_instance()
    print(f"\n注册表中共有 {len(registry)} 个元素快照：")
    for key, snapshot in registry.all_snapshots().items():
        print(f"  [{key}]")
        print(f"    tag={snapshot.tag}, xpath={snapshot.xpath}")
        print(f"    text={snapshot.text!r}, classes={snapshot.classes}")

    # ── 6. 查看监控统计报告 ──
    print("\n" + monitor.report())


if __name__ == "__main__":
    main()
