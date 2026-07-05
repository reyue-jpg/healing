"""
全局元素注册表（单例）。

快照按 URL 划分层级：Dict[url, Dict[locator_key, WebElementData]]。
同一 URL 下可以有多个元素快照，每个快照以原始定位器为键。
所有拦截器实例共享同一个注册表，无需手动传递。
"""
from __future__ import annotations

import threading
from typing import Dict, Optional, Tuple, Union

from headling.models.web_element_data import WebElementData


# 定位器键类型：（定位方式, 定位值）或路径字符串
LocatorKey = Union[Tuple[str, str], str]


class ElementRegistry:
    """
    线程安全的全局元素注册表（单例），按 URL 划分快照存储。

    使用方式：
        registry = ElementRegistry.get_instance()
        registry.register(url, (By.ID, "kw"), element_data)
        snapshot = registry.get(url, (By.ID, "kw"))

    注册表内部结构：
        _store: Dict[str, Dict[str, WebElementData]]
        外层键：url 字符串
        内层键：_make_key(locator) 序列化后的字符串
    """

    _instance: Optional["ElementRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ElementRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # 外层: url -> { locator_key -> WebElementData }
                cls._instance._store: Dict[str, Dict[str, WebElementData]] = {}
                cls._instance._rw_lock = threading.RLock()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ElementRegistry":
        return cls()

    @staticmethod
    def _make_key(locator: LocatorKey) -> str:
        """统一序列化 locator。"""
        if isinstance(locator, tuple):
            by, value = locator
            return f"{by}::{value}"
        return str(locator)

    def register(self, url: str, locator: LocatorKey, data: WebElementData) -> None:
        """
        注册一个元素快照（按 URL 隔离）。

        :param url: 元素所属页面的 URL
        :param locator: (By.xxx, "value") 或 xpath 字符串
        :param data: WebElementData 实例
        """
        key = self._make_key(locator)
        with self._rw_lock:
            if url not in self._store:
                self._store[url] = {}
            self._store[url][key] = data

    def get(self, url: str, locator: LocatorKey) -> Optional[WebElementData]:
        """
        通过 url + locator 查询最近一次成功定位时的元素快照。

        :param url: 元素所属页面的 URL
        :param locator: (By.xxx, "value") 或 xpath 字符串
        :return: WebElementData 或 None
        """
        key = self._make_key(locator)
        with self._rw_lock:
            return self._store.get(url, {}).get(key)

    def get_by_xpath(self, url: str, xpath: str) -> Optional[WebElementData]:
        """通过 url + XPath 字符串直接查询。"""
        return self.get(url, xpath)

    def all_snapshots(self) -> Dict[str, Dict[str, WebElementData]]:
        """
        返回所有快照的完整副本（按 URL 分组，线程安全）。
        返回格式：{ url: { locator_key: WebElementData } }
        """
        with self._rw_lock:
            return {url: dict(locators) for url, locators in self._store.items()}

    def snapshots_by_url(self, url: str) -> Dict[str, WebElementData]:
        """返回指定 URL 下的所有快照副本。"""
        with self._rw_lock:
            return dict(self._store.get(url, {}))

    def remove(self, url: str, locator: LocatorKey) -> None:
        """从注册表中移除指定 URL 下的一条记录。"""
        key = self._make_key(locator)
        with self._rw_lock:
            if url in self._store:
                self._store[url].pop(key, None)
                if not self._store[url]:
                    self._store.pop(url, None)

    def clear(self) -> None:
        """清空注册表（测试或重置用）。"""
        with self._rw_lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._rw_lock:
            return sum(len(locators) for locators in self._store.values())

    def __repr__(self) -> str:
        with self._rw_lock:
            return f"<ElementRegistry urls={len(self._store)} entries={sum(len(v) for v in self._store.values())}>"
