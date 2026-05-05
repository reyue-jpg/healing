"""
healing/dom_parser.py

DOM 解析工具层。

职责：
  从 page_source（HTML 字符串）+ WebElementData 快照中提取
  规则引擎需要的"当前页面上下文"信息，填充 ContextFact。

依赖：html.parser（标准库，无需额外安装）
不依赖 BeautifulSoup，保持与 requirements.txt 的一致性。
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

from models.web_element_data import WebElementData
from facts import ContextFact


# ─────────────────────────────────────────────────────────────────────────────
# XPath 工具函数
# ─────────────────────────────────────────────────────────────────────────────

def extract_parent_xpath(xpath: str) -> str:
    """
    从绝对 XPath 中截取父级路径。

    示例：
      "//*[@id='form']/div/input[2]"  →  "//*[@id='form']/div"
      "//*[@id='kw']"                 →  ""   （顶级 id 定位，无父级）
      "//div/span[1]"                 →  "//div"
    """
    if not xpath:
        return ""
    # 找最后一个 '/' 的位置（不含 '//' 开头的情况）
    last_slash = xpath.rfind("/")
    if last_slash <= 1:   # 只有 "//tag" 形式，无父级
        return ""
    return xpath[:last_slash]


def extract_position_index(xpath: str) -> Optional[int]:
    """
    从 XPath 末尾节点中提取位置索引。

    示例：
      "//div/input[2]"    →  2
      "//div/input"       →  None
      "//*[@id='kw']"     →  None
    """
    match = re.search(r'\[(\d+)\]$', xpath)
    if match:
        return int(match.group(1))
    return None


def estimate_dom_depth(xpath: str) -> int:
    """
    估算 XPath 对应的 DOM 深度（'/' 数量 - 1，'//' 按 2 层计）。

    示例：
      "//div"                →  1
      "//div/span"           →  2
      "//*[@id='a']/div/p"   →  2
    """
    if not xpath:
        return 0
    # 去掉开头的 '//' 后按 '/' 分割
    stripped = xpath.lstrip("/")
    parts = [p for p in stripped.split("/") if p]
    return len(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 轻量级 HTML 解析器（仅用于统计 tag 数量 / 提取文本）
# ─────────────────────────────────────────────────────────────────────────────

class _TagCounter(HTMLParser):
    """统计页面中特定 tag 出现的次数。"""

    def __init__(self, target_tag: str):
        super().__init__()
        self.target_tag = target_tag.lower()
        self.count = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == self.target_tag:
            self.count += 1


class _TextExtractor(HTMLParser):
    """提取页面中所有可见文本（简化版，忽略 script/style）。"""

    def __init__(self):
        super().__init__()
        self._texts: List[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag.lower() in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            text = data.strip()
            if text:
                self._texts.append(text)

    @property
    def texts(self) -> List[str]:
        return self._texts


class _FormParser(HTMLParser):
    """提取页面中 form 的 id，以及 form 内各控件的 tag/type。"""

    def __init__(self):
        super().__init__()
        self.forms: List[Dict] = []          # [{"id": "...", "controls": [...]}]
        self._current_form: Optional[Dict] = None

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag.lower() == "form":
            self._current_form = {
                "id":       attr_dict.get("id", ""),
                "controls": [],
            }
            self.forms.append(self._current_form)
        elif tag.lower() in ("input", "select", "textarea", "button"):
            if self._current_form is not None:
                self._current_form["controls"].append({
                    "tag":  tag.lower(),
                    "type": attr_dict.get("type", ""),
                    "name": attr_dict.get("name", ""),
                })

    def handle_endtag(self, tag):
        if tag.lower() == "form":
            self._current_form = None


# ─────────────────────────────────────────────────────────────────────────────
# 对外接口：build_context_fact
# ─────────────────────────────────────────────────────────────────────────────

def build_context_fact(
    snapshot: WebElementData,
    page_source: str,
) -> ContextFact:
    """
    综合快照信息和当前页面 DOM，构造 ContextFact。

    :param snapshot:    历史元素快照（WebElementData）
    :param page_source: driver.page_source（当前 HTML 字符串）
    :return:            填充好的 ContextFact 实例
    """
    xpath = snapshot.xpath or ""
    tag   = (snapshot.tag or "").lower()

    # ── 从 XPath 直接推算的字段 ──────────────────────────────────────────────
    parent_xpath   = extract_parent_xpath(xpath)
    position_index = extract_position_index(xpath)
    dom_depth      = estimate_dom_depth(xpath)

    # ── 需要解析 DOM 的字段 ──────────────────────────────────────────────────

    # R011：同 tag 元素数量
    same_tag_count = _count_tags(page_source, tag) if tag else 0

    # R005：邻近兄弟文本
    sibling_text = _find_sibling_text(
        page_source,
        snapshot.text or "",
        tag,
        min_length=5,
    )

    # R006：所属 form id
    form_id = _find_form_id(page_source, tag, snapshot.attributes or {})

    return ContextFact(
        parent_xpath   = parent_xpath,
        position_index = position_index,
        same_tag_count = same_tag_count,
        sibling_text   = sibling_text,
        form_id        = form_id,
        dom_depth      = dom_depth,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 内部实现
# ─────────────────────────────────────────────────────────────────────────────

def _count_tags(page_source: str, tag: str) -> int:
    """统计页面中指定 tag 的出现次数。"""
    try:
        counter = _TagCounter(tag)
        counter.feed(page_source)
        return counter.count
    except Exception:
        return 0


def _find_sibling_text(
    page_source: str,
    element_text: str,
    tag: str,
    min_length: int = 5,
) -> str:
    """
    在页面文本中找与目标元素相邻的稳定文本（长度 > min_length）。
    策略：提取页面所有文本块，找包含目标元素文本的相邻块。
    若目标元素本身无文本，则返回页面中第一个满足长度要求的文本块。
    """
    try:
        extractor = _TextExtractor()
        extractor.feed(page_source)
        texts = [t for t in extractor.texts if len(t) > min_length]

        if not texts:
            return ""

        if element_text and len(element_text) > min_length:
            # 找目标文本的相邻块
            for i, t in enumerate(texts):
                if element_text in t or t in element_text:
                    # 返回前一个或后一个非空相邻块
                    if i > 0:
                        return texts[i - 1]
                    if i < len(texts) - 1:
                        return texts[i + 1]

        # 找不到邻近，返回页面第一个稳定文本
        return texts[0] if texts else ""

    except Exception:
        return ""


def _find_form_id(
    page_source: str,
    tag: str,
    attributes: Dict[str, str],
) -> str:
    """
    在页面中找包含目标控件的 form 的 id。
    匹配策略：form 内的控件 name 属性与快照一致。
    """
    if tag not in ("input", "select", "textarea", "button"):
        return ""

    try:
        parser = _FormParser()
        parser.feed(page_source)

        target_name = attributes.get("name", "")
        target_type = attributes.get("type", "")

        for form in parser.forms:
            if not form["id"]:
                continue
            for ctrl in form["controls"]:
                # name 匹配优先，其次 type 匹配
                if target_name and ctrl["name"] == target_name:
                    return form["id"]
                if target_type and ctrl["type"] == target_type:
                    return form["id"]

        return ""

    except Exception:
        return ""
