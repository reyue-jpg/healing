"""
healing/facts.py

experta 事实定义层。

三类事实：
  ElementFact  —— 从 WebElementData 快照派生，代表"历史元素状态"
  ContextFact  —— 从当前页面 DOM 解析派生，代表"当前页面上下文信息"
  HealingResult—— 规则推理成功后写入的结论

设计原则：
  Fact 只存数据，不含任何推理逻辑。
  所有推理逻辑在 HealingEngine 的 @Rule 方法里。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from experta import Fact, Field

from models.web_element_data import WebElementData


# ─────────────────────────────────────────────────────────────────────────────
# ElementFact —— 历史快照翻译为 experta 事实
# ─────────────────────────────────────────────────────────────────────────────
class ElementFact(Fact):
    """
    代表历史上成功定位过的元素状态。
    由 ElementRegistry 里的 WebElementData 快照转换而来。
    """
    tag        = Field(str,  mandatory=True)
    text       = Field(str,  mandatory=False)
    xpath      = Field(str,  mandatory=False)   # 上次成功时的绝对 XPath
    name       = Field(str,  mandatory=False)
    value      = Field(str,  mandatory=False)
    classes    = Field(list, mandatory=False)
    attributes = Field(dict, mandatory=False)   # 全量 HTML 属性字典

    @classmethod
    def from_snapshot(cls, snapshot: WebElementData) -> "ElementFact":
        return cls(
            tag        = snapshot.tag        or "",
            text       = (snapshot.text      or "").strip(),
            xpath      = snapshot.xpath      or "",
            name       = snapshot.name       or "",
            value      = snapshot.value      or "",
            classes    = list(snapshot.classes      or []),
            attributes = dict(snapshot.attributes   or {}),
        )


# ─────────────────────────────────────────────────────────────────────────────
# ContextFact —— 当前页面 DOM 解析结果（供需要实时 DOM 信息的规则使用）
# ─────────────────────────────────────────────────────────────────────────────
class ContextFact(Fact):
    """
    代表当前页面的 DOM 上下文信息。
    由 DomParser 解析 page_source 后注入，供 R005 / R011 等需要
    实时 DOM 数据的规则使用。

    注意：experta 1.9.4 的 Field(int) 不接受 None，
    所以可为 None 的数值字段统一用 Field(object) 声明。
    """
    # 父级 XPath（从历史 xpath 截取末尾节点之前的部分）
    parent_xpath     = Field(str,    mandatory=False)

    # 历史 xpath 末尾的位置索引，如 input[2] 中的 2；无索引时为 None
    position_index   = Field(object, mandatory=False)   # int | None

    # 当前页面同 tag 元素的总数（供 R011 使用）
    same_tag_count   = Field(object, mandatory=False)   # int | None

    # 邻近兄弟元素的稳定文本（供 R005 使用）
    sibling_text     = Field(str,    mandatory=False)

    # 所属 form 的 id（供 R006 使用）
    form_id          = Field(str,    mandatory=False)

    # 历史 XPath 的 DOM 深度（'/' 分隔符数量 - 1）
    dom_depth        = Field(object, mandatory=False)   # int | None


# ─────────────────────────────────────────────────────────────────────────────
# HealingResult —— 规则推理成功后写入的结论
# ─────────────────────────────────────────────────────────────────────────────
class HealingResult(Fact):
    """
    规则触发后 declare 的结论事实。
    调用方从工作内存查询此事实取得推断结果。
    """
    xpath    = Field(str, mandatory=True)   # 推断出的新 XPath
    rule_id  = Field(str, mandatory=True)   # 命中的规则 ID（如 "R001"）
    priority = Field(int, mandatory=True)   # 规则优先级（数字越小越优先）

    @property
    def success(self) -> bool:
        """与 SeleniumInterceptor 的调用约定对齐：result.success"""
        return bool(self["xpath"])

    @property
    def new_xpath(self) -> str:
        """与 SeleniumInterceptor 的调用约定对齐：result.new_xpath"""
        return self["xpath"]
