"""
使用包装器封装 Selenium WebElement，使每次操作（click、send_keys 等）
都经过拦截，同时将元素的原始定位器信息携带在包装对象上，
供自愈引擎在 StaleElementReferenceException 时回查注册表。

设计原则：
  - 不修改 WebElement 类本身（避免全局污染）
  - 每次 find_element 成功后，由拦截器生成 WrappedElement 返回给调用方
  - WrappedElement 的接口与原生 WebElement 一致（通过 __getattr__ 透传）
"""
from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Callable, Optional

from utils.logutil import get_logger
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement

if TYPE_CHECKING:
    from headling.registry.element_registry import ElementRegistry, LocatorKey
else:
    # runtime 时避免循环导入，只作类型提示占位
    ElementRegistry = None
    LocatorKey = None

logger = get_logger()


# 需要拦截的操作方法集合
_INTERCEPTED_ACTIONS = frozenset(
    [
        "click",
        "send_keys",
        "clear",
        "submit",
        "get_attribute",
        "get_property",
        "is_displayed",
        "is_enabled",
        "is_selected",
    ]
)



class WrappedElement:
    """
    WebElement 的透明包装器。

    携带 url + 原始定位器，用于 StaleElement 时的自愈回查。
    url 参数确保快照按页面隔离，同一定位器值在不同页面下不会相互混淆。
    对指定操作方法做拦截（记录 + 异常捕获）。
    其他属性和方法通过 __getattr__ 无损透传。
    """

    def __init__(
        self,
        element: WebElement,
        url: str,
        locator: "LocatorKey",
        registry: "ElementRegistry",
        monitor: Optional[Any] = None,
        healer: Optional[Any] = None,
    ) -> None:
        object.__setattr__(self, "_element", element)
        object.__setattr__(self, "_url", url)
        object.__setattr__(self, "_locator", locator)
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_monitor", monitor)
        object.__setattr__(self, "_healer", healer)

    def __getattr__(self, name: str) -> Any:
        """透传原生 WebElement 的属性和方法。"""
        element = object.__getattribute__(self, "_element")
        attr = getattr(element, name)

        if name in _INTERCEPTED_ACTIONS and callable(attr):
            return self._wrap_action(name, attr)

        return attr

    @property
    def tag_name(self) -> str:
        """常用属性直接透传，减少 __getattr__ 开销。"""
        return object.__getattribute__(self, "_element").tag_name

    @property
    def text(self) -> str:
        return object.__getattribute__(self, "_element").text

    @property
    def id(self) -> str:
        return object.__getattribute__(self, "_element").id

    def _wrap_action(self, method_name: str, func: Callable) -> Callable:
        """返回包装了异常处理与监控记录的可调用对象。"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = object.__getattribute__(self, "_monitor")
            url = object.__getattribute__(self, "_url")
            locator = object.__getattribute__(self, "_locator")
            registry = object.__getattribute__(self, "_registry")
            healer = object.__getattribute__(self, "_healer")

            if monitor:
                monitor.record_action_attempt(url, locator, method_name, args)

            try:
                result = func(*args, **kwargs)
                if monitor:
                    monitor.record_action_success(url, locator, method_name)
                return result

            except StaleElementReferenceException as exc:
                logger.warning(
                    "元素发生 Stale 异常，url=%s 方法=%s 定位器=%s 错误=%s",
                    url, method_name, locator, exc,
                )
                if monitor:
                    monitor.record_stale(url, locator, method_name, exc)

                recovered = self._attempt_recovery(url, locator, registry, healer, monitor)
                if recovered is not None:
                    logger.info("Stale 元素恢复成功，url=%s 准备重试方法=%s", url, method_name)
                    object.__setattr__(self, "_element", recovered)
                    return getattr(recovered, method_name)(*args, **kwargs)

                raise

        return wrapper

    def _attempt_recovery(
        self,
        url: str,
        locator: "LocatorKey",
        registry: "ElementRegistry",
        healer: Optional[Any],
        monitor: Optional[Any],
    ) -> Optional[WebElement]:
        """
        从注册表按 url 查历史快照，调用 healer 获得新 XPath，
        再通过 driver.find_element 重新定位元素。

        :return: 新的原生 WebElement，或 None（恢复失败）
        """
        if healer is None:
            return None

        snapshot = registry.get(url, locator)
        if snapshot is None:
            logger.debug("注册表中无快照，无法恢复元素: url=%s locator=%s", url, locator)
            return None

        try:
            driver = object.__getattribute__(self, "_element").parent
            result = healer.heal(snapshot, driver.page_source)
            if result and result.success:
                from selenium.webdriver.common.by import By

                new_element = driver.find_element(By.XPATH, result.new_xpath)
                if monitor:
                    monitor.record_healing_success(url, locator, result.new_xpath)
                return new_element
        except Exception as exc:
            logger.error("自愈恢复失败: url=%s locator=%s error=%s", url, locator, exc)
            if monitor:
                monitor.record_healing_failure(url, locator, str(exc))

        return None

    def __class_getitem__(cls, item):
        """保持包装器在泛型场景下的兼容行为。"""
        return cls

    def __repr__(self) -> str:
        url = object.__getattribute__(self, "_url")
        locator = object.__getattribute__(self, "_locator")
        element = object.__getattribute__(self, "_element")
        return f"<WrappedElement url={url!r} locator={locator} element={element!r}>"


if __name__ == "__main__":
    """
    本地调试：不启动真实浏览器，用假元素验证
    透传、监控钩子、Stale + 自愈重试 三条路径。
    """
    import logging

    from headling.registry.element_registry import ElementRegistry

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s %(name)s %(message)s",
    )

    class _PrintMonitor:
        """最小监控桩，打印事件便于观察拦截流程。"""

        def record_action_attempt(self, url, locator, method_name, args):
            print(f"[monitor] attempt  url={url!r} locator={locator!r} method={method_name} args={args!r}")

        def record_action_success(self, url, locator, method_name):
            print(f"[monitor] success  url={url!r} locator={locator!r} method={method_name}")

        def record_stale(self, url, locator, method_name, exc):
            print(f"[monitor] stale    url={url!r} locator={locator!r} method={method_name} exc={exc!r}")

        def record_healing_success(self, url, locator, new_xpath):
            print(f"[monitor] heal_ok  url={url!r} locator={locator!r} new_xpath={new_xpath!r}")

        def record_healing_failure(self, url, locator, error):
            print(f"[monitor] heal_fail url={url!r} locator={locator!r} error={error!r}")

    class _FakeDriver:
        page_source = "<html><body><button id='b'>OK</button></body></html>"

        def find_element(self, by, value):
            return _FakeElementAfterHeal(self, healed=True)

    class _FakeElementAfterHeal:
        def __init__(self, parent, healed=False):
            self.parent = parent
            self._healed = healed

        tag_name = "button"
        text = "OK"
        id = "b-new"

        def click(self):
            print(f"[fake element] click()  healed={self._healed}")

    class _FakeElementStaleOnClick:
        """第一次 click 抛 Stale；自愈后包装器会换成 _FakeElementAfterHeal 再点一次。"""

        tag_name = "button"
        text = "OK"
        id = "b-old"

        def __init__(self, driver):
            self.parent = driver

        def click(self):
            raise StaleElementReferenceException()

    class _FakeHealResult:
        def __init__(self):
            self.success = True
            self.new_xpath = "//button[@id='b']"

    class _FakeHealer:
        def heal(self, snapshot, page_source):
            print(f"[fake healer] heal() snapshot.tag={snapshot.tag!r} page_len={len(page_source)}")
            return _FakeHealResult()

    class _FakeElementHappy:
        tag_name = "a"
        text = "link"
        id = "x1"

        def click(self):
            print("[fake element] happy click()")

        def get_attribute(self, name):
            return f"attr:{name}"