"""
Monitor —— 运行时监控器。

记录所有 find_element、action、healing 事件，
支持输出统计报告。
可作为可选参数传入 SeleniumInterceptor。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from utils.logutil import get_logger
from headling.registry.element_registry import LocatorKey

logger = get_logger()


@dataclass
class FindRecord:
    url: str
    locator: LocatorKey
    timestamp: float
    success: bool
    error: Optional[str] = None


@dataclass
class ActionRecord:
    url: str
    locator: LocatorKey
    method: str
    timestamp: float
    success: bool
    error: Optional[str] = None


@dataclass
class HealingRecord:
    url: str
    locator: LocatorKey
    timestamp: float
    success: bool
    new_xpath: Optional[str] = None
    error: Optional[str] = None


class Monitor:
    """
    运行时事件监控器（可选组件）。

    使用方式：
        monitor = Monitor()
        with SeleniumInterceptor(driver, monitor=monitor) as d:
            ...
        print(monitor.report())
    """

    def __init__(self) -> None:
        self._find_records: List[FindRecord] = []
        self._action_records: List[ActionRecord] = []
        self._healing_records: List[HealingRecord] = []

    def record_find_attempt(self, url: str, locator: LocatorKey) -> None:
        """记录查找尝试（仅 DEBUG 日志，不追加到列表，避免与 success/failure 重复）。"""
        logger.debug("[Monitor] find_attempt: url=%s locator=%s", url, locator)

    def record_find_success(self, url: str, locator: LocatorKey, result: Any) -> None:
        """记录查找成功。"""
        self._find_records.append(
            FindRecord(url=url, locator=locator, timestamp=time.time(), success=True)
        )
        logger.debug("[Monitor] find_success: url=%s locator=%s", url, locator)

    def record_find_failure(self, url: str, locator: LocatorKey, exc: Exception) -> None:
        """记录查找失败。"""
        self._find_records.append(
            FindRecord(
                url=url,
                locator=locator,
                timestamp=time.time(),
                success=False,
                error=str(exc),
            )
        )
        logger.warning("[Monitor] find_failure: url=%s locator=%s, error=%s", url, locator, exc)

    def record_action_attempt(
        self, url: str, locator: LocatorKey, method: str, args: Any
    ) -> None:
        """记录操作尝试。"""
        logger.debug("[Monitor] action_attempt: %s on url=%s locator=%s", method, url, locator)

    def record_action_success(self, url: str, locator: LocatorKey, method: str) -> None:
        """记录操作成功。"""
        self._action_records.append(
            ActionRecord(
                url=url,
                locator=locator,
                method=method,
                timestamp=time.time(),
                success=True,
            )
        )

    def record_stale(
        self, url: str, locator: LocatorKey, method: str, exc: Exception
    ) -> None:
        """记录 stale 异常。"""
        self._action_records.append(
            ActionRecord(
                url=url,
                locator=locator,
                method=method,
                timestamp=time.time(),
                success=False,
                error=f"StaleElement: {exc}",
            )
        )
        logger.warning(
            "[Monitor] stale_element: %s on url=%s locator=%s", method, url, locator
        )

    def record_healing_success(self, url: str, locator: LocatorKey, new_xpath: str) -> None:
        """记录自愈成功。"""
        self._healing_records.append(
            HealingRecord(
                url=url,
                locator=locator,
                timestamp=time.time(),
                success=True,
                new_xpath=new_xpath,
            )
        )
        logger.info("[Monitor] healing_success: url=%s locator=%s -> %s", url, locator, new_xpath)

    def record_healing_failure(self, url: str, locator: LocatorKey, error: str) -> None:
        """记录自愈失败。"""
        self._healing_records.append(
            HealingRecord(
                url=url,
                locator=locator,
                timestamp=time.time(),
                success=False,
                error=error,
            )
        )
        logger.error("[Monitor] healing_failure: url=%s locator=%s, error=%s", url, locator, error)

    def report(self) -> str:
        """生成运行统计报告。"""
        find_total = len(self._find_records)
        find_ok = sum(1 for r in self._find_records if r.success)
        find_fail = find_total - find_ok

        action_total = len(self._action_records)
        action_ok = sum(1 for r in self._action_records if r.success)

        heal_total = len(self._healing_records)
        heal_ok = sum(1 for r in self._healing_records if r.success)

        lines = [
            "=" * 50,
            "  自愈监控报告",
            "=" * 50,
            f"  find_element:  总计={find_total}  成功={find_ok}  失败={find_fail}",
            f"  actions:       总计={action_total}  成功={action_ok}",
            f"  healing:       总计={heal_total}  成功={heal_ok}",
            "=" * 50,
        ]

        if self._healing_records:
            lines.append("  自愈详情:")
            for record in self._healing_records:
                status = "✓" if record.success else "✗"
                lines.append(
                    f"    [{status}] url={record.url} locator={record.locator} -> {record.new_xpath or record.error}"
                )

        return "\n".join(lines)
