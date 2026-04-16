"""
兼容层：保留历史导入路径 `pickleWebElement`。

实际实现已迁移到 `headling.security.secure_pickle`。
"""

from headling.security.secure_pickle import SecurePickle, SecurityError

__all__ = ["SecurePickle", "SecurityError"]