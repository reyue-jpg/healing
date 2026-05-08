"""
healing.py —— headling 框架演示与验证脚本。

用法：
    python healing.py

本脚本演示：
  1. 通过 SeleniumDriver 初始化 Chrome 浏览器
  2. 用 SeleniumInterceptor 包装 driver，自动拦截所有 find_element / 操作
  3. 绑定 Monitor（运行时监控）和 HealingEngine（自愈引擎）
  4. 在 https://www.baidu.com 上执行一组真实操作
  5. 退出时打印监控报告

无需修改任何代码即可直接运行。
"""

from selenium.webdriver.common.by import By

from selenium_exec import SeleniumDriver
from headling.interceptor.selenium_interceptor import SeleniumInterceptor
from headling.runtime.monitor import Monitor
from headling.healing_engine import HealingEngine


def main():
    # ── 1. 初始化浏览器 ──────────────────────────────────────────────────────
    print("=" * 60)
    print("headling 自愈框架演示")
    print("=" * 60)
    print("\n[1] 初始化浏览器 ...")

    selenium_driver = SeleniumDriver()
    driver = selenium_driver.get_driver("chrome", "https://www.baidu.com")

    # ── 2. 初始化监控器 ────────────────────────────────────────────────────
    monitor = Monitor()

    # ── 3. 用拦截器包装 driver ──────────────────────────────────────────────
    print("\n[2] 激活 SeleniumInterceptor（拦截 find_element + 操作）...")
    print("    绑定 Monitor + HealingEngine，自愈引擎已就绪。\n")

    with SeleniumInterceptor(
        driver,
        monitor=monitor,
        healer=HealingEngine(),
        auto_heal=True,
    ) as d:

        # ── 3a. 正常查找元素（自动注册快照）────────────────────────────────
        print("[3a] find_element: 百度搜索框（By.ID, 'chat-textarea'）")
        search_box = d.find_element(By.ID, "chat-textarea")
        print(f"       找到元素: <{search_box.tag_name}>  text='{search_box.text}'")

        # ── 3b. 正常操作元素（自动记录事件）────────────────────────────────
        print("\n[3b] send_keys + clear（拦截操作，全程记录）")
        search_box.send_keys("Selenium 自愈框架")
        print("       已输入文本。")

        search_box.clear()
        print("       已清空。")

        # ── 3c. 再次查找（验证注册表快照复用）────────────────────────────
        print("\n[3c] find_element: 百度搜索按钮（By.ID, 'chat-submit-button'）")
        search_btn = d.find_element(By.ID, "chat-submit-button")
        print(f"       找到元素: <{search_btn.tag_name}>  text='{search_btn.text}'")

        # ── 3d. 演示点击操作（触发 JS 执行，此处不真正等待页面跳转）──────
        print("\n[3d] click 搜索按钮（触发页面跳转，模拟点击）")
        search_btn.click()
        print("       点击完成，等待页面加载 ...")
        d.implicitly_wait(3)

        # ── 3e. 演示 StaleElement 自愈 ────────────────────────────────────
        print("\n[3e] 演示 StaleElementReferenceException 自愈流程")
        print("       （正常情况下不会触发，仅展示概念）")
        print("       触发路径：元素过期 → WrappedElement 捕获异常 →")
        print("                 查询注册表 → HealingEngine 推理新 XPath → 重试")
        print("       当前场景：元素仍然有效，未触发自愈。")

    # ── 4. 退出拦截器，打印监控报告 ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("运行报告")
    print("=" * 60)
    print(monitor.report())

    # ── 5. 关闭浏览器 ──────────────────────────────────────────────────────
    print("\n[5] 关闭浏览器。")
    selenium_driver.quit_driver()
    print("\n演示完成。headling 框架运行正常。\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n脚本执行出错: {exc}")
        raise
