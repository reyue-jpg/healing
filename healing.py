"""
healing.py — headling 自愈框架演示 & 集成测试

核心测试目标：
  验证"历史定位器失效后，自愈引擎能否通过快照中的其他稳定属性重建定位"。

Registry key 机制（按 URL 隔离）：
  - 快照以 "url + 原始定位器" 为复合 key 注册到注册表
  - 自愈时，用 "当前 url + 原始定位器" 去注册表查找快照
  - 因此，必须先用历史定位器（By.ID）成功定位一次，才会注册快照
  - 不同页面的同一定位器（如 id="submit"）互不干扰

快照结构：
  {
    "http://example.com/page1": {
      "id::dynamicTarget": WebElementData(...),
      ...
    },
    ...
  }

测试流程（两次运行）：

  第一次运行（注册阶段）：
    1. 清除 sessionStorage → 刷新 → JS 将 id 初始化为 "dynamicTarget"
    2. 通过 By.ID, "dynamicTarget" 首次定位成功
    3. 拦截器注册快照：url=file://... key=('id', 'dynamicTarget')
       快照包含：tag=div, id=dynamicTarget, class, data-anchor=main-target, text=...
    4. 退出时持久化到 plk_element.json

  第二次运行（自愈阶段）：
    1. 加载持久化快照（url + key 仍为同一组合）
    2. 加载页面，JS 将 id 切换为另一个（如 "widget-alpha"）
    3. 用 By.ID, "dynamicTarget" 定位 → 失败
    4. 拦截器查询注册表（按 url） → 找到快照
    5. HealingEngine 推理新 XPath（用 data-anchor + 文本组合）
    6. 新 XPath 在当前页面验证成功 → 自愈完成
"""

import os
import time

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from headling.interceptor.selenium_interceptor import SeleniumInterceptor
from headling.runtime.monitor import Monitor
from headling.healing_engine import HealingEngine


def main():
    print("=" * 60)
    print("headling 自愈框架演示")
    print("=" * 60)

    service = Service(executable_path=r"./selenium_driver/chromedriver.exe")
    driver = Chrome(service=service)
    monitor = Monitor()

    html_path = os.path.abspath(
        r"C:\Users\REDYUE\Downloads\point_html_20260508_f5b14f.html"
    )

    with SeleniumInterceptor(
        driver,
        monitor=monitor,
        healer=HealingEngine(),
        auto_heal=True,
        persist_file="plk_element.json"
    ) as d:

        # ── 阶段 1：初始化，清除 sessionStorage ─────────────────────────
        print("\n[阶段1] 初始化测试环境")
        d.get(f"file:///{html_path}")
        d.execute_script("sessionStorage.clear();")
        print("       sessionStorage 已清除，刷新后 id 将初始化为 'dynamicTarget'")
        d.refresh()
        time.sleep(4)

        # ── 阶段 2：通过历史定位器首次定位（注册快照）─────────────────
        print("\n[阶段2] 首次定位（By.ID, 'dynamicTarget'）— 注册快照")
        target = d.find_element(By.ID, "dynamicTarget")
        current_id = target.get_attribute("id")
        current_class = target.get_attribute("class")
        print(f"       找到元素: <{target.tag_name}>  id={current_id}")
        print(f"       class={current_class}")

        # ── 阶段 3：刷新页面，id 变化，模拟历史定位器失效 ───────────
        print("\n[阶段3] 刷新页面，模拟页面结构变化（id 将变为另一个值）")
        d.refresh()
        time.sleep(4)

        actual_ids = d.find_elements(By.XPATH, "//div[@data-anchor='main-target']")
        if actual_ids:
            print(f"       刷新后 id={actual_ids[0].get_attribute('id')}（不再是 'dynamicTarget'）")
        else:
            print("       注意：data-anchor 元素未找到（可能 JS 未执行）")

        # ── 阶段 4：再次用历史定位器定位，触发自愈 ───────────────────
        print("\n[阶段4] 用历史定位器 By.ID, 'dynamicTarget' 再次定位")
        print("       预期：id 已变化 → NoSuchElementException →")
        print("                  → 拦截器查询注册表 → HealingEngine 推理 → 自愈")

        try:
            healed = d.find_element(By.ID, "dynamicTarget")
            print(f"       ✓ 自愈成功：找到了 <{healed.tag_name}>  id={healed.get_attribute('id')}")
        except Exception as exc:
            print(f"       定位失败（符合预期）: {exc.__class__.__name__}")
            print("       （自愈失败 → 无历史快照 → 元素确实不可定位）")

        # ── 阶段 5：验证 data-anchor 稳定定位 ──────────────────────────
        print("\n[阶段5] 通过稳定属性定位，验证元素可找到")
        stable = d.find_element(By.XPATH, "//div[@data-anchor='main-target']")
        print(f"       找到元素: <{stable.tag_name}>  id={stable.get_attribute('id')}")
        print("       data-anchor 始终不变，可用于推理重建定位器")

    # ── 打印监控报告 ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("运行报告")
    print("=" * 60)
    print(monitor.report())

    # ── 关闭浏览器 ────────────────────────────────────────────────────
    print("\n快照已持久化到 plk_element.json")
    print("第二次运行时，上次失败的 By.ID 定位将触发引擎自愈\n")
    d.quit()
    print("演示完成。\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n脚本执行出错: {exc}")
        raise
