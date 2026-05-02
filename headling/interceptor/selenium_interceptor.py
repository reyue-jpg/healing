"""
SeleniumInterceptor —— 全局 Selenium 拦截器。

用法：
    driver = Chrome(...)

    with SeleniumInterceptor(driver) as d:
        d.get("https://example.com")
        elem = d.find_element(By.ID, "kw")   # 自动创建元素快照并缓存
        elem.click()                           # 自动拦截，异常时走自愈流程

设计要点：
  1. 通过闭包替换 driver.find_element 和 driver.find_elements
  2. 在退出上下文时还原原始方法，driver 恢复干净状态
  3. ElementRegistry 是全局单例，多个拦截器实例共享同一注册表
  4. 每次 find_element 成功后自动创建 WebElementData 并写入注册表
  5. 返回 WrappedElement，携带定位器信息，透明包装原生 WebElement
"""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable, Optional

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from utils.logutil import get_logger
from headling.interceptor.element_wrapper import WrappedElement
from headling.models.web_element_data import WebElementData
from headling.registry.element_registry import ElementRegistry, LocatorKey

logger = get_logger()


class SeleniumInterceptor:
    """
    Selenium 全局拦截器（上下文管理器）。

    参数:
        driver: 已初始化的 WebDriver 实例
        monitor: 可选监控对象，需实现 record_* 接口
        healer: 可选自愈引擎，需实现 heal(snapshot, page_source) 接口
        auto_heal: 是否在 find_element 失败时自动触发自愈（默认 True）
    """

    registry: ElementRegistry = ElementRegistry.get_instance()

    def __init__(
        self,
        driver: WebDriver,
        monitor: Optional[Any] = None,
        healer: Optional[Any] = None,
        auto_heal: bool = True,
    ) -> None:
        self._driver = driver
        self._monitor = monitor
        self._healer = healer
        self._auto_heal = auto_heal

        self._original_find_element = driver.find_element
        self._original_find_elements = driver.find_elements

    def __enter__(self) -> WebDriver:
        """替换 driver 方法并返回 driver。"""
        self._patch_driver()
        logger.debug("SeleniumInterceptor 已激活: driver=%s", self._driver)
        return self._driver

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """还原 driver 方法。"""
        self._restore_driver()
        logger.debug("SeleniumInterceptor 已退出，driver 方法已还原")
        return False

    def _patch_driver(self) -> None:
        """替换 driver.find_element 与 driver.find_elements。"""
        self._driver.find_element = self._make_find_element_wrapper(
            self._original_find_element, single=True
        )
        self._driver.find_elements = self._make_find_element_wrapper(
            self._original_find_elements, single=False
        )

    def _restore_driver(self) -> None:
        """还原原始方法。"""
        self._driver.find_element = self._original_find_element
        self._driver.find_elements = self._original_find_elements

    def _make_find_element_wrapper(
        self, original: Callable, single: bool
    ) -> Callable:
        """
        生成包装了拦截逻辑的 find_element 或 find_elements 方法。

        :param original: 原始方法（已绑定到 driver）
        :param single: True 表示 find_element，False 表示 find_elements
        """
        interceptor = self

        @functools.wraps(original)
        def wrapper(by: str, value: str):
            locator: LocatorKey = (by, value)

            if interceptor._monitor:
                interceptor._monitor.record_find_attempt(locator)

            try:
                raw_result = original(by, value)
            except (NoSuchElementException, StaleElementReferenceException) as exc:
                logger.warning("查找元素失败: locator=%s, exc=%s", locator, exc)

                if interceptor._monitor:
                    interceptor._monitor.record_find_failure(locator, exc)

                if interceptor._auto_heal and interceptor._healer:
                    healed = interceptor._attempt_heal(locator)
                    if healed is not None:
                        return healed

                raise

            if single:
                wrapped = interceptor._wrap_and_register(raw_result, locator)
                if interceptor._monitor:
                    interceptor._monitor.record_find_success(locator, wrapped)
                return wrapped

            wrapped_list = [
                interceptor._wrap_and_register(el, locator)
                for el in raw_result
            ]
            if interceptor._monitor:
                interceptor._monitor.record_find_success(locator, wrapped_list)
            return wrapped_list

        return wrapper

    def _wrap_and_register(
        self, element: WebElement, locator: LocatorKey
    ) -> WrappedElement:
        """
        1. 从原生 WebElement 创建 WebElementData 快照
        2. 写入全局注册表（key = locator）
        3. 返回 WrappedElement（透明包装 WebElement）
        """
        try:
            snapshot = WebElementData.from_selenium_element(
                element,
                include_attributes=True,
            )
            self.registry.register(locator, snapshot)
            logger.debug(
                "已注册元素快照: locator=%s, tag=<%s> xpath=%s",
                locator,
                snapshot.tag,
                snapshot.xpath,
            )
        except Exception as exc:
            logger.warning("WebElementData 快照失败（忽略）: %s", exc)

        return WrappedElement(
            element=element,
            locator=locator,
            registry=self.registry,
            monitor=self._monitor,
            healer=self._healer,
        )

    def _attempt_heal(self, locator: LocatorKey) -> Optional[WrappedElement]:
        """
        在 find_element 失败后，从注册表取历史快照并尝试自愈。

        :return: 新的 WrappedElement，或 None（自愈失败）
        """
        snapshot = self.registry.get(locator)
        if snapshot is None:
            logger.debug("注册表中无历史快照，跳过自愈: locator=%s", locator)
            return None

        try:
            page_source = self._driver.page_source
            result = self._healer.heal(snapshot, page_source)

            if result and result.success:
                logger.info("自愈成功: 新 XPath = %s", result.new_xpath)
                new_element = self._original_find_element(By.XPATH, result.new_xpath)

                if self._monitor:
                    self._monitor.record_healing_success(locator, result.new_xpath)

                return self._wrap_and_register(new_element, locator)

        except Exception as exc:
            logger.error("自愈过程出现异常: %s", exc)
            if self._monitor:
                self._monitor.record_healing_failure(locator, str(exc))

        return None

    @property
    def snapshots(self):
        """返回当前注册表中所有元素快照的副本。"""
        return self.registry.all_snapshots()
