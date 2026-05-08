"""
test_healing_engine.py

对 HealingEngine 12 条规则逐一进行单元测试。
不需要真实浏览器，直接构造 WebElementData 快照 + mock page_source。
"""

from headling.healing_engine import HealingEngine
from headling.models.web_element_data import WebElementData


def _heal(snapshot: WebElementData, page_source: str = "<html></html>"):
    return HealingEngine.run_healing(snapshot, page_source)


def _snap(**kwargs) -> WebElementData:
    """快速构造 WebElementData 快照。"""
    defaults = dict(
        tag="input", element_id="", name="", value="",
        text="", xpath="", classes=[], attributes={}
    )
    defaults.update(kwargs)
    return WebElementData(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# R001  精确多属性匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R001():
    snap = _snap(
        tag="input",
        attributes={"name": "username", "type": "text"},
        xpath="//input[@id='old']",
    )
    result = _heal(snap)
    assert result is not None, "R001 应命中"
    assert result["rule_id"] == "R001", f"应命中 R001，实际={result['rule_id']}"
    assert "@name='username'" in result["xpath"]
    assert "@type='text'" in result["xpath"]
    print(f"  ✓ R001: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R002  单关键属性 + 文本匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R002():
    # 只有 1 个高权重属性，但有文本
    snap = _snap(
        tag="button",
        text="立即提交表单",
        attributes={"type": "submit"},   # 只有 1 个高权重属性
        xpath="//button[@id='old']",
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R002", f"应命中 R002，实际={result['rule_id']}"
    assert "contains(text()" in result["xpath"]
    print(f"  ✓ R002: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R003  父级上下文 + 属性匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R003():
    # 有父级 xpath，只有 1 个高权重属性，无文本
    snap = _snap(
        tag="input",
        text="",
        attributes={"name": "email"},
        xpath="//div[@class='form']/input",   # 父级可解析
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R003", f"应命中 R003，实际={result['rule_id']}"
    assert "//div[@class='form']" in result["xpath"]
    print(f"  ✓ R003: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R004  相对位置索引匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R004():
    # 父级可解析，xpath 含位置索引，无稳定属性，无文本
    snap = _snap(
        tag="li",
        text="",
        attributes={},
        xpath="//ul[@id='nav']/li[3]",
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R004", f"应命中 R004，实际={result['rule_id']}"
    assert "li[3]" in result["xpath"]
    print(f"  ✓ R004: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R005  邻近文本锚点匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R005():
    # 无稳定属性，无父级，有邻近文本（在 page_source 里）
    snap = _snap(
        tag="input",
        text="",
        attributes={},
        xpath="//input",
    )
    page_source = """
    <html><body>
      <label>请输入您的用户名</label>
      <input type="text" />
    </body></html>
    """
    result = _heal(snap, page_source)
    assert result is not None
    assert result["rule_id"] == "R005", f"应命中 R005，实际={result['rule_id']}"
    assert "following::input" in result["xpath"]
    print(f"  ✓ R005: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R006  表单序列匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R006():
    # 只有 type 一个高权重属性（确保 R001/R002 不触发），无文本，有 form
    snap = _snap(
        tag="input",
        text="",
        attributes={"type": "password"},   # 只有 type，R001 需要 ≥2 个才触发
        xpath="//input",
    )
    page_source = """
    <html><body>
      <form id="loginForm">
        <input type="text" name="user" />
        <input type="password" name="pwd" />
      </form>
    </body></html>
    """
    result = _heal(snap, page_source)
    assert result is not None
    assert result["rule_id"] == "R006", f"应命中 R006，实际={result['rule_id']}"
    assert "loginForm" in result["xpath"]
    assert "password" in result["xpath"]
    print(f"  ✓ R006: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R007  模糊属性部分匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R007():
    # 属性值较长，有稳定前缀，无高权重属性
    snap = _snap(
        tag="div",
        text="",
        attributes={"data-component": "user-profile-card-2024"},
        xpath="//div",
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R007", f"应命中 R007，实际={result['rule_id']}"
    assert "contains(@data-component" in result["xpath"]
    print(f"  ✓ R007: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R008  组合类名匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R008():
    snap = _snap(
        tag="button",
        text="",
        classes=["btn", "btn-primary", "submit-action"],
        attributes={},
        xpath="//button",
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R008", f"应命中 R008，实际={result['rule_id']}"
    assert "contains(@class" in result["xpath"]
    print(f"  ✓ R008: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R009  角色语义匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R009():
    snap = _snap(
        tag="div",
        text="",
        classes=[],
        attributes={"role": "navigation"},
        xpath="//div",
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R009", f"应命中 R009，实际={result['rule_id']}"
    assert "@role='navigation'" in result["xpath"]
    print(f"  ✓ R009: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R010  结构深度过滤匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R010():
    # 浅层元素，xpath 深度 < 5，无其他有效属性
    snap = _snap(
        tag="nav",
        text="",
        classes=[],
        attributes={},
        xpath="//body/nav",   # 深度 = 2
    )
    result = _heal(snap)
    assert result is not None
    assert result["rule_id"] == "R010", f"应命中 R010，实际={result['rule_id']}"
    assert "ancestor::*" in result["xpath"]
    print(f"  ✓ R010: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R011  类型分组匹配
# ─────────────────────────────────────────────────────────────────────────────
def test_R011():
    snap = _snap(
        tag="aside",
        text="",
        classes=[],
        attributes={},   # 无稳定属性
        # xpath 不含位置索引，DOM 深度 >= 5 让 R010 不触发
        xpath="//body/div/section/article/aside",
    )
    # page_source 中只有 2 个 aside（< 3），R011 应命中
    page_source = "<html><body><div><aside/><aside/></div></body></html>"
    result = _heal(snap, page_source)
    assert result is not None
    assert result["rule_id"] == "R011", f"应命中 R011，实际={result['rule_id']}"
    assert "(//aside)" in result["xpath"]
    print(f"  ✓ R011: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# R012  兜底策略
# ─────────────────────────────────────────────────────────────────────────────
def test_R012():
    # 所有信息极度匮乏，只有 tag 和历史 xpath（不含位置索引避免 R004 触发）
    # DOM 深度 >= 5 避免 R010 触发，同类元素 >= 3 避免 R011 触发
    snap = _snap(
        tag="span",
        text="",
        classes=[],
        attributes={},
        xpath="//div/section/article/p/span",  # 深度 5，无位置索引
    )
    # page_source 中有大量 span（> 3），R011 不会触发
    page_source = "<html>" + "<span/>" * 10 + "</html>"
    result = _heal(snap, page_source)
    assert result is not None
    assert result["rule_id"] == "R012", f"应命中 R012，实际={result['rule_id']}"
    assert "position()" in result["xpath"]
    print(f"  ✓ R012: {result['xpath']}")


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("R001 精确多属性匹配",     test_R001),
        ("R002 单属性+文本匹配",    test_R002),
        ("R003 父级上下文+属性",    test_R003),
        ("R004 相对位置索引",       test_R004),
        ("R005 邻近文本锚点",       test_R005),
        ("R006 表单序列匹配",       test_R006),
        ("R007 模糊属性部分匹配",   test_R007),
        ("R008 组合类名匹配",       test_R008),
        ("R009 角色语义匹配",       test_R009),
        ("R010 结构深度过滤",       test_R010),
        ("R011 类型分组匹配",       test_R011),
        ("R012 兜底策略",           test_R012),
    ]

    passed, failed = 0, 0
    for name, fn in tests:
        try:
            print(f"测试 {name}:")
            fn()
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            failed += 1

    print()
    print(f"{'='*50}")
    print(f"结果: {passed} 通过 / {failed} 失败 / 共 {len(tests)} 条")
    print(f"{'='*50}")
    if failed:
        sys.exit(1)
