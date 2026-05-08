"""
headling/healing_engine.py

核心自愈引擎。

基于 experta 专家系统，将历史元素快照（ElementFact）和当前页面上下文
（ContextFact）作为工作内存，按优先级依次尝试 12 条规则，推断出新的
XPath 并用 driver.find_element 验证可用性后返回 HealingResult。

规则优先级（priority 越小越优先）：
  R001  精确多属性匹配          priority=1
  R002  单属性 + 文本匹配       priority=2
  R003  父级上下文 + 属性       priority=3
  R004  相对位置索引匹配        priority=4
  R005  邻近文本锚点匹配        priority=5
  R006  表单序列匹配            priority=6
  R007  模糊属性部分匹配        priority=7
  R008  组合类名匹配            priority=8
  R009  角色语义匹配            priority=9
  R010  结构深度过滤匹配        priority=10
  R011  类型分组匹配            priority=11
  R012  兜底策略                priority=12

对外接口：
  HealingEngine.heal(snapshot, page_source, driver=None) -> HealingResult | None
  HealingEngine.run_healing(snapshot, page_source)       -> dict | None
      （无 driver，仅推断 XPath，供单元测试使用）
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from experta import (
    KnowledgeEngine, Rule, MATCH, NOT, OR, AND,
    DefFacts, Field, Fact, W, L, P, TEST
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from utils.logutil import get_logger
from headling.models.web_element_data import WebElementData
from headling.dom_parser import build_context_fact
from headling.facts import ElementFact, ContextFact, HealingResult

logger = get_logger()

# 高权重属性：稳定性强，适合精确匹配
_HIGH_WEIGHT_ATTRS = {"name", "id", "type", "data-testid", "data-id",
                      "data-cy", "data-qa", "aria-label", "placeholder",
                      "for", "href", "action"}

# 属性值最短前缀长度，用于 R007 模糊匹配
_FUZZY_PREFIX_MIN_LEN = 4


def _high_weight_attrs(attributes: dict) -> Dict[str, str]:
    """从属性字典中筛选出高权重属性。"""
    return {k: v for k, v in (attributes or {}).items()
            if k in _HIGH_WEIGHT_ATTRS and v}


def _build_attr_conditions(attrs: Dict[str, str]) -> str:
    """将属性字典拼成 XPath 条件串，如 [@name='x'][@type='text']。"""
    return "".join(f"[@{k}='{v}']" for k, v in attrs.items())


def _extract_parent_xpath(xpath: str) -> str:
    """截取 XPath 父级路径。"""
    if not xpath:
        return ""
    last_slash = xpath.rfind("/")
    if last_slash <= 1:
        return ""
    return xpath[:last_slash]


def _extract_position_index(xpath: str) -> Optional[int]:
    """提取 XPath 末尾位置索引。"""
    import re
    m = re.search(r'\[(\d+)\]$', xpath)
    return int(m.group(1)) if m else None


def _estimate_dom_depth(xpath: str) -> int:
    """估算 XPath DOM 深度。"""
    if not xpath:
        return 0
    stripped = xpath.lstrip("/")
    parts = [p for p in stripped.split("/") if p]
    return len(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 内部推断引擎（experta KnowledgeEngine）
# ─────────────────────────────────────────────────────────────────────────────

class _HealingKE(KnowledgeEngine):
    """
    experta 规则引擎。

    每次实例化后：
      1. reset()
      2. declare(ElementFact, ContextFact)
      3. run()
      4. 从 _candidates 取优先级最小的结果
    """

    def __init__(self):
        super().__init__()
        # 收集所有触发的候选结果，最终取 priority 最小的
        self._candidates: List[Dict[str, Any]] = []

    def _add_candidate(self, xpath: str, rule_id: str, priority: int) -> None:
        """规则触发后调用，加入候选列表。"""
        self._candidates.append({
            "xpath": xpath,
            "rule_id": rule_id,
            "priority": priority,
        })
        logger.debug("[%s] 候选 XPath: %s", rule_id, xpath)

    def best_candidate(self) -> Optional[Dict[str, Any]]:
        """返回 priority 最小的候选结果。"""
        if not self._candidates:
            return None
        return min(self._candidates, key=lambda c: c["priority"])

    # ── R001 精确多属性匹配 ────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) >= 2),
    )
    def r001_multi_attr_match(self, tag, attributes):
        hw = _high_weight_attrs(attributes)
        conditions = _build_attr_conditions(hw)
        xpath = f"//{tag}{conditions}"
        self._add_candidate(xpath, "R001", 1)

    # ── R002 单属性 + 文本匹配 ────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, text=MATCH.text, attributes=MATCH.attributes),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 1),
        TEST(lambda text: bool(text and len(text.strip()) >= 2)),
    )
    def r002_single_attr_text(self, tag, text, attributes):
        hw = _high_weight_attrs(attributes)
        conditions = _build_attr_conditions(hw)
        short_text = text.strip()[:40]
        xpath = f"//{tag}{conditions}[contains(text(),'{short_text}')]"
        self._add_candidate(xpath, "R002", 2)

    # ── R003 父级上下文 + 属性匹配 ────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, xpath=MATCH.xpath,
                    text=MATCH.text, attributes=MATCH.attributes),
        TEST(lambda xpath: bool(_extract_parent_xpath(xpath))),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) >= 1),
        TEST(lambda text: not text or not text.strip()),
    )
    def r003_parent_context_attr(self, tag, xpath, attributes):
        parent = _extract_parent_xpath(xpath)
        hw = _high_weight_attrs(attributes)
        conditions = _build_attr_conditions(hw)
        result_xpath = f"{parent}/{tag}{conditions}"
        self._add_candidate(result_xpath, "R003", 3)

    # ── R004 相对位置索引匹配 ────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, xpath=MATCH.xpath,
                    text=MATCH.text, attributes=MATCH.attributes),
        TEST(lambda xpath: bool(_extract_parent_xpath(xpath))),
        TEST(lambda xpath: _extract_position_index(xpath) is not None),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda text: not text or not text.strip()),
    )
    def r004_position_index(self, tag, xpath):
        parent = _extract_parent_xpath(xpath)
        idx = _extract_position_index(xpath)
        result_xpath = f"{parent}/{tag}[{idx}]"
        self._add_candidate(result_xpath, "R004", 4)

    # ── R005 邻近文本锚点匹配 ────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes, text=MATCH.text),
        ContextFact(sibling_text=MATCH.sibling_text),
        TEST(lambda sibling_text: bool(sibling_text and len(sibling_text) >= 5)),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
    )
    def r005_sibling_text_anchor(self, tag, sibling_text):
        short = sibling_text.strip()[:40].replace("'", "\\'")
        xpath = f"//*[contains(text(),'{short}')]/following::{tag}"
        self._add_candidate(xpath, "R005", 5)

    # ── R006 表单序列匹配 ────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes, text=MATCH.text),
        ContextFact(form_id=MATCH.form_id),
        TEST(lambda form_id: bool(form_id)),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) <= 1),
        TEST(lambda text: not text or not text.strip()),
    )
    def r006_form_sequence(self, tag, attributes, form_id):
        hw = _high_weight_attrs(attributes)
        if hw:
            conditions = _build_attr_conditions(hw)
        else:
            # 用 type 属性兜底（若存在）
            type_val = (attributes or {}).get("type", "")
            conditions = f"[@type='{type_val}']" if type_val else ""
        xpath = f"//*[@id='{form_id}']//{tag}{conditions}"
        self._add_candidate(xpath, "R006", 6)

    # ── R007 模糊属性部分匹配 ────────────────────────────────────────────
    # 排除 class、role 等已由专用规则处理的属性
    _R007_EXCLUDE = {"class", "role", "aria-label", "placeholder"}

    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes),
        TEST(lambda attributes: any(
            len(v) > 8
            for k, v in (attributes or {}).items()
            if k not in _HealingKE._R007_EXCLUDE and k not in _HIGH_WEIGHT_ATTRS and v
        )),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda attributes: not (attributes or {}).get("role")),
    )
    def r007_fuzzy_attr(self, tag, attributes):
        exclude = self._R007_EXCLUDE | _HIGH_WEIGHT_ATTRS
        best_k, best_v = max(
            ((k, v) for k, v in (attributes or {}).items()
             if k not in exclude and v and len(v) > 8),
            key=lambda kv: len(kv[1]),
        )
        prefix = best_v[:max(_FUZZY_PREFIX_MIN_LEN, len(best_v) // 2)]
        xpath = f"//{tag}[contains(@{best_k},'{prefix}')]"
        self._add_candidate(xpath, "R007", 7)

    # ── R008 组合类名匹配 ────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes),
        TEST(lambda attributes: (
            isinstance((attributes or {}).get("class", ""), str) and
            len((attributes or {}).get("class", "").split()) >= 2
        ) or False),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
    )
    def r008_combined_class_from_attr(self, tag, attributes):
        class_str = attributes.get("class", "")
        parts = class_str.split()
        cls1, cls2 = parts[0], parts[1]
        xpath = (f"//{tag}[contains(@class,'{cls1}') and "
                 f"contains(@class,'{cls2}')]")
        self._add_candidate(xpath, "R008", 8)

    @Rule(
        ElementFact(tag=MATCH.tag, classes=MATCH.classes, attributes=MATCH.attributes),
        TEST(lambda classes: bool(classes) and len(classes) >= 2),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda attributes: not (attributes or {}).get("class")),
    )
    def r008_combined_class_from_classes(self, tag, classes, attributes):
        cls1, cls2 = classes[0], classes[1]
        xpath = (f"//{tag}[contains(@class,'{cls1}') and "
                 f"contains(@class,'{cls2}')]")
        self._add_candidate(xpath, "R008", 8)

    # ── R009 角色语义匹配 ────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, attributes=MATCH.attributes),
        TEST(lambda attributes: bool((attributes or {}).get("role"))),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
    )
    def r009_role_semantic(self, tag, attributes):
        role = attributes["role"]
        xpath = f"//{tag}[@role='{role}']"
        self._add_candidate(xpath, "R009", 9)

    # ── R010 结构深度过滤匹配 ────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, xpath=MATCH.xpath,
                    classes=MATCH.classes, attributes=MATCH.attributes),
        TEST(lambda xpath: 0 < _estimate_dom_depth(xpath) < 5),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda classes: not classes),
    )
    def r010_structural_depth(self, tag, xpath):
        depth = _estimate_dom_depth(xpath)
        xpath_result = f"//{tag}[count(ancestor::*)={depth - 1}]"
        self._add_candidate(xpath_result, "R010", 10)

    # ── R011 类型分组匹配 ────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, xpath=MATCH.xpath,
                    classes=MATCH.classes, attributes=MATCH.attributes),
        ContextFact(same_tag_count=MATCH.same_tag_count),
        TEST(lambda same_tag_count: (
            isinstance(same_tag_count, int) and 0 < same_tag_count < 3
        )),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda classes: not classes),
        TEST(lambda xpath: _estimate_dom_depth(xpath) >= 5),
        TEST(lambda xpath: _extract_position_index(xpath) is None),
    )
    def r011_type_group(self, tag, same_tag_count):
        xpath = f"(//{ tag })[{same_tag_count}]"
        self._add_candidate(xpath, "R011", 11)

    # ── R012 兜底策略 ────────────────────────────────────────────────────
    @Rule(
        ElementFact(tag=MATCH.tag, xpath=MATCH.xpath,
                    classes=MATCH.classes, attributes=MATCH.attributes),
        ContextFact(same_tag_count=MATCH.same_tag_count),
        TEST(lambda attributes: len(_high_weight_attrs(attributes)) == 0),
        TEST(lambda classes: not classes),
        TEST(lambda xpath: _estimate_dom_depth(xpath) >= 5),
        TEST(lambda xpath: _extract_position_index(xpath) is None),
        TEST(lambda same_tag_count: (
            not isinstance(same_tag_count, int) or same_tag_count >= 3
        )),
    )
    def r012_fallback(self, tag, xpath):
        depth = _estimate_dom_depth(xpath)
        xpath_result = (
            f"//{tag}[count(ancestor::*)={depth - 1} and "
            f"position()=1]"
        )
        self._add_candidate(xpath_result, "R012", 12)


# ─────────────────────────────────────────────────────────────────────────────
# 对外门面：HealingEngine
# ─────────────────────────────────────────────────────────────────────────────

class HealingEngine:
    """
    自愈引擎门面类。

    典型调用方式（SeleniumInterceptor 内部）：
        engine = HealingEngine()
        result = engine.heal(snapshot, page_source, driver)
        if result and result.success:
            new_element = driver.find_element(By.XPATH, result.new_xpath)

    单元测试（无 driver）：
        raw = HealingEngine.run_healing(snapshot, page_source)
        # raw -> {"xpath": ..., "rule_id": ..., "priority": ...} | None
    """

    # ── 静态工厂：纯推断，不验证（供测试） ──────────────────────────────

    @staticmethod
    def run_healing(
        snapshot: WebElementData,
        page_source: str = "<html></html>",
    ) -> Optional[Dict[str, Any]]:
        """
        仅执行规则推断，不用 driver 验证 XPath 是否可用。
        返回优先级最高的候选字典，或 None。
        """
        engine = _HealingKE()
        engine.reset()

        element_fact = ElementFact.from_snapshot(snapshot)
        context_fact = build_context_fact(snapshot, page_source)

        engine.declare(element_fact)
        engine.declare(context_fact)
        engine.run()

        return engine.best_candidate()

    # ── 实例方法：推断 + driver 验证 ─────────────────────────────────────

    def heal(
        self,
        snapshot: WebElementData,
        page_source: str,
        driver: Optional[WebDriver] = None,
    ) -> Optional[HealingResult]:
        """
        推断新 XPath，若提供 driver 则逐候选验证可用性，返回 HealingResult。

        :param snapshot:    历史元素快照
        :param page_source: 当前页面 HTML（driver.page_source）
        :param driver:      WebDriver 实例，用于验证 XPath 可用性
        :return:            HealingResult 或 None（所有候选均无效）
        """
        engine = _HealingKE()
        engine.reset()

        element_fact = ElementFact.from_snapshot(snapshot)
        context_fact = build_context_fact(snapshot, page_source)

        engine.declare(element_fact)
        engine.declare(context_fact)
        engine.run()

        candidates = sorted(engine._candidates, key=lambda c: c["priority"])

        if not candidates:
            logger.warning(
                "自愈引擎：无规则命中。tag=%s xpath=%s",
                snapshot.tag, snapshot.xpath,
            )
            return None

        if driver is None:
            # 没有 driver，直接返回优先级最高的候选
            best = candidates[0]
            logger.info(
                "自愈推断（未验证）：[%s] %s", best["rule_id"], best["xpath"]
            )
            return HealingResult(
                xpath=best["xpath"],
                rule_id=best["rule_id"],
                priority=best["priority"],
            )

        # 有 driver：按优先级逐一验证
        for candidate in candidates:
            xpath = candidate["xpath"]
            rule_id = candidate["rule_id"]
            priority = candidate["priority"]

            try:
                driver.find_element(By.XPATH, xpath)
                logger.info(
                    "自愈验证成功：[%s] priority=%d xpath=%s",
                    rule_id, priority, xpath,
                )
                return HealingResult(
                    xpath=xpath,
                    rule_id=rule_id,
                    priority=priority,
                )
            except Exception as exc:
                logger.debug(
                    "候选无效：[%s] %s -> %s", rule_id, xpath, exc
                )
                continue

        logger.warning(
            "自愈失败：所有 %d 个候选 XPath 均无法定位元素。tag=%s",
            len(candidates), snapshot.tag,
        )
        return None
