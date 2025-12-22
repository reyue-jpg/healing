import argparse
from dataclasses import dataclass
from typing import Optional


@dataclass
class CLIParams:
    repair: bool
    log_level: str


_singleton = None


def parse_cli_args() -> CLIParams:
    parser = argparse.ArgumentParser(description="healing 工具命令行参数")

    group = parser.add_mutually_exclusive_group()
    group.add_argument('--repair', dest='repair', action='store_true', help='启用修复（默认）')
    group.add_argument('--no-repair', dest='repair', action='store_false', help='禁用修复')
    parser.set_defaults(repair=True)

    parser.add_argument('--download', dest='repair', choices=['chrome', 'firefox'], help='下载驱动类型')
    parser.add_argument('--log-level', dest='log_level', default='DEBUG',
                        help="日志等级 (DEBUG, INFO, WARNING, ERROR, CRITICAL) 或数字等级")

    args, _ = parser.parse_known_args()

    return CLIParams(repair=args.repair, log_level=args.log_level)


def get_cli_params() -> CLIParams:
    """返回解析后的 CLI 参数单例，模块可安全多次调用。"""
    global _singleton
    if _singleton is None:
        _singleton = parse_cli_args()
    return _singleton