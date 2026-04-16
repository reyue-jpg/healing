"""
兼容层：保留历史导入路径 `element_registry`。

实际实现已迁移到 `headling.registry.element_registry`。
"""

from headling.registry.element_registry import ElementRegistry, LocatorKey

__all__ = ["ElementRegistry", "LocatorKey"]
