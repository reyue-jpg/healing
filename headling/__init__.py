"""
headling 包入口。

该包用于统一管理 Selenium 自愈相关模块，避免根目录散落文件。
"""

from headling.models.web_element_data import WebElementData
from headling.registry.element_registry import ElementRegistry, LocatorKey
from headling.interceptor.element_wrapper import WrappedElement
from headling.interceptor.selenium_interceptor import SeleniumInterceptor
from headling.runtime.monitor import Monitor
from headling.security.secure_pickle import SecurePickle, SecurityError
from headling.healing_engine import HealingEngine
from headling.facts import ElementFact, ContextFact, HealingResult

__auth__ = 'FUHAO'

# 在程序启动时打印 ASCII 艺术字标志。
printLogo = """
      _   _                  _   _                 
     | | | |   ___    __ _  | | (_)  _ __     __ _ 
     | |_| |  / _ \  / _` | | | | | | '_ \   / _` |
     |  _  | |  __/ | (_| | | | | | | | | | | (_| |
     |_| |_|  \___|  \__,_| |_| |_| |_| |_|  \__, |
                                             |___/ 
"""
print(printLogo)

__all__ = [
    "WebElementData",
    "ElementRegistry",
    "LocatorKey",
    "WrappedElement",
    "SeleniumInterceptor",
    "Monitor",
    "SecurePickle",
    "SecurityError",
    "HealingEngine",
    "HealingResult",
    "ElementFact",
    "ContextFact",
]
