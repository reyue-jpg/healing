"""
兼容层：保留历史导入路径 `selenium_interceptor`。

实际实现已迁移到 `headling.interceptor.selenium_interceptor`。
"""

from headling.interceptor.selenium_interceptor import SeleniumInterceptor

__all__ = ["SeleniumInterceptor"]
