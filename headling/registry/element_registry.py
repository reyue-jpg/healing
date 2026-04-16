"""
全局元素注册表（单例）。

- key: locator 元组 (by, value) 或 xpath 字符串
- value: WebElementData 快照
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
    线程安全的全局元素注册表（单例）。

    使用方式：
        registry = ElementRegistry.get_instance()
        registry.register((By.ID, "kw"), element_data)
        snapshot = registry.get((By.ID, "kw"))
    """

    _instance: Optional["ElementRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ElementRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._store: Dict[str, WebElementData] = {}
                cls._instance._rw_lock = threading.RLock()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ElementRegistry":
        return cls()

    @staticmethod
    def _make_key(locator: LocatorKey) -> str:
        """统一序列化 key。"""
        if isinstance(locator, tuple):
            by, value = locator
            return f"{by}::{value}"
        return str(locator)

    def register(self, locator: LocatorKey, data: WebElementData) -> None:
        """
        注册一个元素快照。

        :param locator: (By.xxx, "value") 或 xpath 字符串
        :param data: WebElementData 实例
        """
        key = self._make_key(locator)
        with self._rw_lock:
            self._store[key] = data

    def get(self, locator: LocatorKey) -> Optional[WebElementData]:
        """
        通过 locator 查询最近一次成功定位时的元素快照。

        :param locator: (By.xxx, "value") 或 xpath 字符串
        :return: WebElementData 或 None
        """
        key = self._make_key(locator)
        with self._rw_lock:
            return self._store.get(key)

    def get_by_xpath(self, xpath: str) -> Optional[WebElementData]:
        """通过 XPath 字符串直接查询。"""
        return self.get(xpath)

    def all_snapshots(self) -> Dict[str, WebElementData]:
        """返回所有快照的副本（线程安全）。"""
        with self._rw_lock:
            return dict(self._store)

    def remove(self, locator: LocatorKey) -> None:
        """从注册表中移除一条记录。"""
        key = self._make_key(locator)
        with self._rw_lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """清空注册表（测试或重置用）。"""
        with self._rw_lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._rw_lock:
            return len(self._store)

    def __repr__(self) -> str:
        return f"<ElementRegistry entries={len(self)}>"
