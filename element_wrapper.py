"""
兼容层：保留历史导入路径 `element_wrapper`。

实际实现已迁移到 `headling.interceptor.element_wrapper`。
"""

from headling.interceptor.element_wrapper import WrappedElement

__all__ = ["WrappedElement"]
