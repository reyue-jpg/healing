"""
test_headling_all.py

Headling 框架核心测试套件（精简版，20 个用例）。

覆盖范围：
  - 规则引擎单元测试（6 条代表性规则）
  - SecurePickle 安全序列化测试
  - ElementRegistry URL 隔离测试
  - WrappedElement 拦截与恢复测试
  - SeleniumInterceptor 上下文管理器测试
  - 4 类典型页面变更场景测试（T1/T2/T5/T6）
  - Baseline 对比测试
  - HealingResult 接口契约测试

无需真实浏览器，所有场景使用 mock 或 HTML 字符串构造。
"""

import json
import os
import sys
import tempfile
import unittest

from selenium.webdriver.common.by import By


# ─────────────────────────────────────────────────────────────────────────────
# 辅助桩（fake objects）
# ─────────────────────────────────────────────────────────────────────────────

class _FakeDriver:
    def __init__(self, page_source="<html></html>", find_element_behavior=None):
        self.page_source = page_source
        self._find_behavior = find_element_behavior or {}
        self.current_url = "http://example.com/page"

    def find_element(self, by, value):
        key = (by, value)
        if key in self._find_behavior:
            result = self._find_behavior[key]
            if isinstance(result, Exception):
                raise result
            return result
        raise Exception(f"No mock for {key}")

    def find_elements(self, by, value):
        key = (by, value)
        if key in self._find_behavior:
            result = self._find_behavior[key]
            if isinstance(result, list):
                return result
            if isinstance(result, Exception):
                raise result
            return [result]
        return []


class _FakeElement:
    def __init__(self, tag="input", attrs=None, parent=None):
        self.tag_name = tag
        self.text = ""
        self.id = "fake-id"
        self._attrs = attrs or {}
        self.parent = parent

    def click(self):
        pass

    def get_attribute(self, name):
        return self._attrs.get(name)


def _snap(**kwargs):
    """快速构造 WebElementData 快照。"""
    from headling.models.web_element_data import WebElementData
    defaults = dict(
        tag="input", element_id="", name="", value="",
        text="", xpath="", classes=[], attributes={},
        url="http://example.com/page",
    )
    defaults.update(kwargs)
    return WebElementData(**defaults)


# ═════════════════════════════════════════════════════════════════════════════
# 1. 规则引擎单元测试（6 条代表性规则，覆盖所有核心匹配策略）
# ═════════════════════════════════════════════════════════════════════════════

class TestHealingRules(unittest.TestCase):
    """覆盖精确匹配、文本匹配、邻近锚点、模糊匹配、类名匹配、兜底策略。"""

    def _heal(self, snapshot, page_source="<html></html>"):
        from headling.healing_engine import HealingEngine
        return HealingEngine.run_healing(snapshot, page_source)

    def test_R001_exact_multi_attr(self):
        """R001：高权重属性 >= 2，生成多条件 XPath。"""
        snap = _snap(
            tag="input",
            attributes={"name": "username", "type": "text"},
            xpath="//input[@id='old']",
        )
        result = self._heal(snap)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R001")
        self.assertIn("@name='username'", result["xpath"])
        self.assertIn("@type='text'", result["xpath"])

    def test_R002_single_attr_text(self):
        """R002：恰好 1 个高权重属性 + 文本，生成 contains(text()) XPath。"""
        snap = _snap(
            tag="button", text="提交",
            attributes={"type": "submit"},
            xpath="//button[@id='old']",
        )
        result = self._heal(snap)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R002")
        self.assertIn("contains(text()", result["xpath"])

    def test_R005_sibling_text_anchor(self):
        """R005：零高权重属性 + 页面含邻近文本，生成 following:: 路径。"""
        snap = _snap(tag="input", text="", attributes={}, xpath="//input")
        page = """
        <html><body>
          <label>请输入您的用户名</label>
          <input type="text" />
        </body></html>
        """
        result = self._heal(snap, page)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R005")
        self.assertIn("following::input", result["xpath"])

    def test_R007_fuzzy_attr(self):
        """R007：属性值长度 > 8，无高权重属性，生成 contains() 前缀匹配。"""
        snap = _snap(
            tag="div", text="",
            attributes={"data-component": "user-profile-card-2024"},
            xpath="//div",
        )
        result = self._heal(snap)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R007")
        self.assertIn("contains(@data-component", result["xpath"])

    def test_R008_combined_class(self):
        """R008：class 属性有 >= 2 个词，无高权重属性。"""
        snap = _snap(
            tag="button", text="",
            attributes={"class": "btn btn-primary submit-action"},
            xpath="//button",
        )
        result = self._heal(snap)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R008")
        self.assertIn("contains(@class", result["xpath"])

    def test_R012_fallback(self):
        """R012：所有规则均不满足，兜底生成 position() 路径。"""
        snap = _snap(
            tag="span", text="",
            attributes={}, classes=[],
            xpath="//div/section/article/p/span",
        )
        page = "<html>" + "".join("<span/>" for _ in range(10)) + "</html>"
        result = self._heal(snap, page)
        self.assertIsNotNone(result)
        self.assertEqual(result["rule_id"], "R012")
        self.assertIn("position()", result["xpath"])


# ═════════════════════════════════════════════════════════════════════════════
# 2. SecurePickle 安全序列化测试（2 个核心用例）
# ═════════════════════════════════════════════════════════════════════════════

class TestSecurePickle(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _tmppath(self, name="test.json"):
        return os.path.join(self._tmpdir, name)

    def test_roundtrip(self):
        """往返序列化不丢失数据。"""
        from headling.security.secure_pickle import SecurePickle
        sp = SecurePickle(file_name=self._tmppath())
        data = {"key": "value", "num": 42}
        sp.to_json_safe(data, self._tmppath())
        loaded = sp.from_json_safe(self._tmppath())
        self.assertEqual(loaded, data)

    def test_tamper_detection(self):
        """签名被篡改时，from_json_safe 应抛出 SecurityError。"""
        from headling.security.secure_pickle import SecurePickle, SecurityError
        sp = SecurePickle(file_name=self._tmppath())
        sp.to_json_safe({"secret": "data"}, self._tmppath())
        # 篡改 JSON 内容
        with open(self._tmppath(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw["data"] = "TAMPERED" + raw["data"][8:]
        with open(self._tmppath(), "w", encoding="utf-8") as f:
            json.dump(raw, f)
        with self.assertRaises(SecurityError):
            sp.from_json_safe(self._tmppath())


# ═════════════════════════════════════════════════════════════════════════════
# 3. ElementRegistry URL 隔离测试（1 个核心用例）
# ═════════════════════════════════════════════════════════════════════════════

class TestElementRegistry(unittest.TestCase):

    def setUp(self):
        from headling.registry.element_registry import ElementRegistry
        self.registry = ElementRegistry()
        self.registry.clear()

    def tearDown(self):
        self.registry.clear()

    def test_url_isolation(self):
        """同一 locator 在不同 URL 下互不干扰。"""
        from headling.models.web_element_data import WebElementData
        snap1 = _snap(tag="div", attributes={"id": "sidebar"})
        snap2 = _snap(tag="nav", attributes={"id": "sidebar"})
        self.registry.register("http://a.com", ("id", "sidebar"), snap1)
        self.registry.register("http://b.com", ("id", "sidebar"), snap2)
        self.assertEqual(self.registry.get("http://a.com", ("id", "sidebar")).tag, "div")
        self.assertEqual(self.registry.get("http://b.com", ("id", "sidebar")).tag, "nav")


# ═════════════════════════════════════════════════════════════════════════════
# 4. WrappedElement 拦截与恢复测试（2 个核心用例）
# ═════════════════════════════════════════════════════════════════════════════

class TestWrappedElement(unittest.TestCase):

    def setUp(self):
        from headling.registry.element_registry import ElementRegistry
        self.registry = ElementRegistry()
        self.registry.clear()

    def tearDown(self):
        self.registry.clear()

    def test_action_passthrough(self):
        """未被拦截的方法直接透传到原生元素。"""
        from headling.interceptor.element_wrapper import WrappedElement
        fake_el = _FakeElement(tag="button", attrs={"id": "btn"})
        fake_el.parent = _FakeDriver()
        wrapped = WrappedElement(
            element=fake_el, url="http://ex.com",
            locator=("id", "btn"), registry=self.registry,
            monitor=None, healer=None,
        )
        self.assertEqual(wrapped.tag_name, "button")
        self.assertEqual(wrapped.get_attribute("id"), "btn")

    def test_stale_triggers_healing(self):
        """StaleElementReferenceException 时，WrappedElement 调用 healer 恢复。"""
        from headling.interceptor.element_wrapper import WrappedElement
        from selenium.common.exceptions import StaleElementReferenceException

        def _raise_stale():
            raise StaleElementReferenceException("mock stale element")

        stale_el = _FakeElement(tag="button", attrs={"id": "old-btn"})
        healed_el = _FakeElement(tag="button", attrs={"id": "new-btn"})
        stale_el.parent = _FakeDriver(
            find_element_behavior={(By.XPATH, "//button[@id='new-btn']"): healed_el},
        )

        # 注册表中的快照须与 wrapped 的 locator 完全一致
        locator = ("id", "old-btn")
        snap = _snap(tag="button", attributes={"id": "old-btn"})
        self.registry.register("http://ex.com", locator, snap)

        class _FakeResult:
            success = True
            new_xpath = "//button[@id='new-btn']"

        class _FakeHealer:
            def heal(self, snapshot, page_source):
                return _FakeResult()

        wrapped = WrappedElement(
            element=stale_el, url="http://ex.com",
            locator=locator, registry=self.registry,
            monitor=None, healer=_FakeHealer(),
        )
        stale_el.click = _raise_stale
        healed_el.click = lambda: None

        wrapped.click()   # 应触发自愈并重试


# ═════════════════════════════════════════════════════════════════════════════
# 5. SeleniumInterceptor 上下文管理器测试（2 个核心用例）
# ═════════════════════════════════════════════════════════════════════════════

class TestSeleniumInterceptor(unittest.TestCase):

    def setUp(self):
        from headling.registry.element_registry import ElementRegistry
        ElementRegistry._instance = None
        self.registry = ElementRegistry()
        self.registry.clear()
        self._tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_context_manager_enter_exit(self):
        """上下文管理器正常激活 / 退出，driver 方法被替换后能还原。"""
        from headling.interceptor.selenium_interceptor import SeleniumInterceptor
        driver = _FakeDriver(page_source="<html></html>")
        icp = SeleniumInterceptor(driver=driver)
        with icp:
            # driver.find_element 已被替换，应为 icp 内部的包装函数
            self.assertIsNot(driver.find_element, icp._original_find_element)
        # __exit__ 后还原
        self.assertEqual(driver.find_element, icp._original_find_element)

    def test_persistence_roundtrip(self):
        """第一个实例写入快照，第二个实例能从同一文件恢复。"""
        from headling.interceptor.selenium_interceptor import SeleniumInterceptor

        snap = _snap(tag="button", attributes={"id": "saved-btn"}, url="http://ex.com")
        persist_path = os.path.join(self._tmpdir, "plk.json")

        # 写入
        icp1 = SeleniumInterceptor(driver=_FakeDriver(), persist_file=persist_path)
        icp1.registry.register("http://ex.com", ("id", "saved-btn"), snap)
        with icp1:
            icp1._flush_registry(persist_path)

        # 恢复
        from headling.registry.element_registry import ElementRegistry
        ElementRegistry._instance = None
        icp2 = SeleniumInterceptor(driver=_FakeDriver(), persist_file=persist_path)
        with icp2:
            icp2._restore_registry(persist_path)
            restored = icp2.registry.get("http://ex.com", ("id", "saved-btn"))
            self.assertIsNotNone(restored)
            self.assertEqual(restored.tag, "button")


# ═════════════════════════════════════════════════════════════════════════════
# 6. 典型页面变更场景测试（T1/T2/T5/T6）
# ═════════════════════════════════════════════════════════════════════════════

class TestChangeScenarios(unittest.TestCase):
    """覆盖结构重排、属性变化、多重变更叠加、元素移除（负面基线）。"""

    def _heal(self, snapshot, page_source):
        from headling.healing_engine import HealingEngine
        return HealingEngine.run_healing(snapshot, page_source)

    def test_T1_dom_structure_change(self):
        """T1：DOM 结构重排，name 属性保留，R001 应命中。"""
        snap = _snap(
            tag="input", text="",
            attributes={"name": "email", "type": "text"},
            xpath="//form[@id='form']/div/input",
        )
        new_page = """
        <html><body>
          <form id="form">
            <div class="wrapper"><div>
              <input name="email" type="text" />
            </div></div>
          </form>
        </body></html>
        """
        result = self._heal(snap, new_page)
        self.assertIsNotNone(result)
        self.assertIn("@name='email'", result["xpath"])

    def test_T2_attribute_value_change(self):
        """T2：id 变化但 name 保留，R001 应命中。"""
        snap = _snap(
            tag="input",
            attributes={"id": "old-id", "name": "username", "type": "text"},
            xpath="//input[@id='old-id']",
        )
        new_page = "<html><body><input id='new-id' name='username' type='text' /></body></html>"
        result = self._heal(snap, new_page)
        self.assertIsNotNone(result)
        self.assertIn("@name='username'", result["xpath"])

    def test_T5_multi_change_overlay(self):
        """T5：id 和 name 均变化，依赖 class 词匹配（R008）。"""
        snap = _snap(
            tag="button", text="提交",
            attributes={"class": "btn btn-primary"},
            xpath="//button[@id='old-submit']",
        )
        new_page = """
        <html><body>
          <button class="btn btn-primary" id="new-submit-id">提交</button>
        </body></html>
        """
        result = self._heal(snap, new_page)
        self.assertIsNotNone(result)
        self.assertIn("contains(@class", result["xpath"])

    def test_T6_element_removed(self):
        """T6（负面基线）：目标元素不存在于变更后页面，规则命中但不保证可定位。"""
        snap = _snap(
            tag="button", text="已删除的内容",
            attributes={"id": "ghost-btn"},
            xpath="//button[@id='ghost-btn']",
        )
        new_page = "<html><body><p>该功能已下线</p></body></html>"
        result = self._heal(snap, new_page)
        # run_healing（无 driver）返回推断结果，不验证可定位性
        if result is not None:
            self.assertIn("xpath", result)
            self.assertIn("rule_id", result)


# ═════════════════════════════════════════════════════════════════════════════
# 7. Baseline 对比测试
# ═════════════════════════════════════════════════════════════════════════════

class TestBaselineComparison(unittest.TestCase):
    """验证 Baseline-A（无干预）遇错即终止，Baseline-B（双冗余 XPath）可覆盖部分场景。"""

    def test_baseline_a_always_fails(self):
        """Baseline-A：元素找不到时直接抛异常。"""
        from selenium.common.exceptions import NoSuchElementException
        driver = _FakeDriver(
            page_source="<html><input id='new-id' /></html>",
            find_element_behavior={("id", "old-id"): NoSuchElementException()},
        )
        with self.assertRaises(NoSuchElementException):
            driver.find_element("id", "old-id")

    def test_baseline_b_partial_coverage(self):
        """Baseline-B：主 XPath 失败后尝试备用 XPath，能覆盖变更场景。"""
        from selenium.common.exceptions import NoSuchElementException

        driver = _FakeDriver(
            page_source="<html><input id='new-id' name='username' /></html>",
            find_element_behavior={
                ("id", "old-id"): NoSuchElementException(),
                (By.XPATH, "//input[@name='username']"): _FakeElement(tag="input"),
            },
        )
        primary = ("id", "old-id")
        fallback = (By.XPATH, "//input[@name='username']")

        # Baseline-B 逻辑：主失败后尝试备用
        def baseline_b_find(driver, by, value):
            try:
                return driver.find_element(by, value)
            except Exception:
                return driver.find_element(*fallback)

        result = baseline_b_find(driver, *primary)
        self.assertIsNotNone(result)


# ═════════════════════════════════════════════════════════════════════════════
# 8. HealingResult 接口契约测试
# ═════════════════════════════════════════════════════════════════════════════

class TestHealingResult(unittest.TestCase):

    def test_success_properties(self):
        """成功结果：success=True，字段正确暴露。"""
        from headling.facts import HealingResult
        result = HealingResult(xpath="//button[@id='btn']", rule_id="R001", priority=1)
        self.assertTrue(result.success)
        self.assertEqual(result.new_xpath, "//button[@id='btn']")
        self.assertEqual(result["rule_id"], "R001")
        self.assertEqual(result["priority"], 1)

    def test_failure_property(self):
        """失败结果（空 xpath）：success=False。"""
        from headling.facts import HealingResult
        result = HealingResult(xpath="", rule_id="R012", priority=12)
        self.assertFalse(result.success)


# ═════════════════════════════════════════════════════════════════════════════
# 运行入口
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for cls in [
        TestHealingRules,
        TestSecurePickle,
        TestElementRegistry,
        TestWrappedElement,
        TestSeleniumInterceptor,
        TestChangeScenarios,
        TestBaselineComparison,
        TestHealingResult,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
