"""
headling/interceptor/selenium_interceptor.py

SeleniumInterceptor —— 全局 Selenium 拦截器（上下文管理器）。

新增持久化支持：
  - __enter__ 时从 persist_file 加载历史快照，恢复注册表
  - __exit__  时将注册表全量保存到 persist_file（HMAC 签名 JSON）
  - persist_file=None 时不做任何持久化（与旧行为完全兼容）

密钥管理：
  - 首次运行自动生成随机密钥，保存到 <persist_file>.key（Base64）
  - 后续运行自动读取同一密钥，确保历史文件可被正确验证
"""
from __future__ import annotations

import functools
import logging
import os
from typing import Any, Callable, Optional

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from utils.logutil import get_logger
from headling.interceptor.element_wrapper import WrappedElement
from headling.models.web_element_data import WebElementData
from headling.registry.element_registry import ElementRegistry, LocatorKey
from headling.security.secure_pickle import SecurePickle, SecurityError

logger = get_logger()


class SeleniumInterceptor:
    """
    Selenium 全局拦截器（上下文管理器）。

    参数:
        driver:       已初始化的 WebDriver 实例
        monitor:      可选监控对象
        healer:       可选自愈引擎
        auto_heal:    find_element 失败时是否自动触发自愈（默认 True）
        persist_file: 元素快照持久化 JSON 路径；None 表示不持久化
    """

    registry: ElementRegistry = ElementRegistry.get_instance()

    def __init__(
        self,
        driver: WebDriver,
        monitor: Optional[Any] = None,
        healer: Optional[Any] = None,
        auto_heal: bool = True,
        persist_file: Optional[str] = None,
    ) -> None:
        self._driver = driver
        self._monitor = monitor
        self._healer = healer
        self._auto_heal = auto_heal
        self._persist_file = persist_file

        self._original_find_element  = driver.find_element
        self._original_find_elements = driver.find_elements

        # 持久化器（仅在指定了 persist_file 时创建）
        self._pickle: Optional[SecurePickle] = None
        if persist_file:
            self._pickle = self._load_or_create_pickle(persist_file)

    # ── 上下文管理 ────────────────────────────────────────────────────────

    def __enter__(self) -> WebDriver:
        # 1. 从磁盘加载历史快照，合并进注册表
        if self._pickle and self._persist_file:
            self._restore_registry(self._persist_file)

        # 2. 替换 driver 方法
        self._patch_driver()
        logger.debug("SeleniumInterceptor 已激活")
        return self._driver

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # 1. 还原 driver 方法
        self._restore_driver()

        # 2. 把注册表全量落盘
        if self._pickle and self._persist_file:
            self._flush_registry(self._persist_file)

        logger.debug("SeleniumInterceptor 已退出，注册表已持久化")
        return False

    # ── 持久化：加载 & 落盘 ───────────────────────────────────────────────

    def _load_or_create_pickle(self, persist_file: str) -> SecurePickle:
        """读取或新建密钥文件，返回 SecurePickle 实例。"""
        key_file = persist_file + ".key"
        if os.path.exists(key_file):
            try:
                with open(key_file, "r") as f:
                    b64_key = f.read().strip()
                sp = SecurePickle.import_key(b64_key, file_name=persist_file)
                logger.debug("已加载已有密钥: %s", key_file)
                return sp
            except Exception as e:
                logger.warning("密钥文件损坏，重新生成: %s", e)

        # 新建密钥并持久化
        sp = SecurePickle(file_name=persist_file)
        os.makedirs(os.path.dirname(os.path.abspath(key_file)), exist_ok=True)
        with open(key_file, "w") as f:
            f.write(sp.export_key())
        logger.debug("已生成新密钥: %s", key_file)
        return sp

    def _restore_registry(self, persist_file: str) -> None:
        """从 JSON 文件加载快照，合并进注册表（不覆盖内存中已有条目）。"""
        if not os.path.exists(persist_file):
            logger.debug("持久化文件不存在，跳过加载: %s", persist_file)
            return
        try:
            snapshots: dict = self._pickle.from_json_safe(persist_file)
            loaded = 0
            for key, data in snapshots.items():
                if self.registry.get(key) is None:   # 不覆盖内存中已有的
                    self.registry.register(key, data)
                    loaded += 1
            logger.info("从磁盘恢复 %d 条元素快照", loaded)
            logger.info(f"  [Persist] 从磁盘加载了 {loaded} 条历史元素快照 ← {persist_file}")
        except (SecurityError, Exception) as e:
            logger.warning("加载持久化文件失败（忽略）: %s", e)
            logger.warning(f"  [Persist] 警告：加载失败（{e}），将从空注册表开始")

    def _flush_registry(self, persist_file: str) -> None:
        """将注册表全量序列化落盘。"""
        try:
            snapshots = self.registry.all_snapshots()
            self._pickle.to_json_safe(snapshots, persist_file)
            logger.info("已将 %d 条快照持久化到: %s", len(snapshots), persist_file)
            logger.info(f"  [Persist] 已将 {len(snapshots)} 条元素快照保存到 → {persist_file}")
        except Exception as e:
            logger.error("持久化注册表失败: %s", e)
            logger.warning(f"  [Persist] 警告：保存失败（{e}）")

    # ── driver 方法替换 ───────────────────────────────────────────────────

    def _patch_driver(self) -> None:
        self._driver.find_element  = self._make_wrapper(self._original_find_element,  single=True)
        self._driver.find_elements = self._make_wrapper(self._original_find_elements, single=False)

    def _restore_driver(self) -> None:
        self._driver.find_element  = self._original_find_element
        self._driver.find_elements = self._original_find_elements

    def _make_wrapper(self, original: Callable, single: bool) -> Callable:
        interceptor = self

        @functools.wraps(original)
        def wrapper(by: str, value: str):
            locator: LocatorKey = (by, value)
            if interceptor._monitor:
                interceptor._monitor.record_find_attempt(locator)
            try:
                raw = original(by, value)
            except (NoSuchElementException, StaleElementReferenceException) as exc:
                logger.warning("查找元素失败: locator=%s", locator)
                if interceptor._monitor:
                    interceptor._monitor.record_find_failure(locator, exc)
                if interceptor._auto_heal and interceptor._healer:
                    healed = interceptor._attempt_heal(locator)
                    if healed is not None:
                        return healed
                raise

            if single:
                wrapped = interceptor._wrap_and_register(raw, locator)
                if interceptor._monitor:
                    interceptor._monitor.record_find_success(locator, wrapped)
                return wrapped

            result = [interceptor._wrap_and_register(el, locator) for el in raw]
            if interceptor._monitor:
                interceptor._monitor.record_find_success(locator, result)
            return result

        return wrapper

    def _wrap_and_register(self, element: WebElement, locator: LocatorKey) -> WrappedElement:
        try:
            snapshot = WebElementData.from_selenium_element(element, include_attributes=True)
            self.registry.register(locator, snapshot)
            logger.debug("已注册快照: locator=%s tag=<%s>", locator, snapshot.tag)
        except Exception as exc:
            logger.warning("快照失败（忽略）: %s", exc)
        return WrappedElement(
            element=element, locator=locator, registry=self.registry,
            monitor=self._monitor, healer=self._healer,
        )

    def _attempt_heal(self, locator: LocatorKey) -> Optional[WrappedElement]:
        snapshot = self.registry.get(locator)
        if snapshot is None:
            logger.debug("注册表无历史快照，跳过自愈: locator=%s", locator)
            return None
        try:
            page_source = self._driver.page_source
            result = self._healer.heal(snapshot, page_source, self._driver)
            if result and result.success:
                logger.info("自愈成功: %s", result.new_xpath)
                new_el = self._original_find_element(By.XPATH, result.new_xpath)
                if self._monitor:
                    self._monitor.record_healing_success(locator, result.new_xpath)
                return self._wrap_and_register(new_el, locator)
        except Exception as exc:
            logger.error("自愈过程异常: %s", exc)
            if self._monitor:
                self._monitor.record_healing_failure(locator, str(exc))
        return None

    @property
    def snapshots(self):
        return self.registry.all_snapshots()