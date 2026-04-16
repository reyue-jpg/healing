"""
兼容迁移层：浏览器驱动实现。

当前直接复用根目录 `selenium_exec.py` 中的 `SeleniumDriver`，
后续可逐步下沉完整实现到包内。
"""

from selenium_exec import SeleniumDriver

__all__ = ["SeleniumDriver"]
