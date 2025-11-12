# selenium_interceptor.py
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from functools import wraps
import inspect


class SeleniumInterceptor:
    def __init__(self, healer, monitor):
        self.healer = healer
        self.monitor = monitor
        self.original_methods = {}

    def patch_driver(self, driver):
        """修补WebDriver方法以启用拦截"""
        self._patch_find_methods(driver)
        self._patch_action_methods(driver)
        return driver

    def _patch_find_methods(self, driver):
        """拦截元素查找方法 - 适配Selenium 4.x语法"""
        # 保存原始方法
        self.original_methods['find_element'] = driver.find_element
        self.original_methods['find_elements'] = driver.find_elements

        # 创建包装器方法
        def find_element_wrapper(by, value):
            return self._find_element_handler(by, value)

        def find_elements_wrapper(by, value):
            return self._find_elements_handler(by, value)

        # 替换方法
        driver.find_element = find_element_wrapper
        driver.find_elements = find_elements_wrapper

    def _find_element_handler(self, by, value):
        """处理find_element方法调用"""
        try:
            # 记录查找尝试
            self.monitor.record_find_attempt('find_element', (by, value), {})

            # 执行原始查找
            result = self.original_methods['find_element'](by, value)

            # 记录成功查找
            self.monitor.record_find_success('find_element', (by, value), {}, result)
            return result

        except (NoSuchElementException, StaleElementReferenceException) as e:
            # 记录查找失败
            self.monitor.record_find_failure('find_element', (by, value), {}, e)

            # 如果启用自动修复，尝试修复
            if self.monitor.auto_heal:
                healed_element = self._attempt_healing(by, value, e)
                if healed_element:
                    return healed_element

            # 重新抛出原始异常
            raise

    def _find_elements_handler(self, by, value):
        """处理find_elements方法调用"""
        try:
            self.monitor.record_find_attempt('find_elements', (by, value), {})
            result = self.original_methods['find_elements'](by, value)
            self.monitor.record_find_success('find_elements', (by, value), {}, result)
            return result

        except (NoSuchElementException, StaleElementReferenceException) as e:
            self.monitor.record_find_failure('find_elements', (by, value), {}, e)

            # 对于find_elements，返回空列表而不是修复
            if self.monitor.auto_heal:
                self.monitor.record_healing_attempt({'type': by, 'value': value},
                                                    "find_elements返回空列表")
            return []

    def _attempt_healing(self, by, value, exception):
        """尝试修复元素查找"""
        # 获取当前页面源码
        driver = self.monitor.get_current_driver()
        page_source = driver.page_source

        # 提取定位器信息
        locator = {'type': by, 'value': value}

        # 调用自愈引擎
        healing_result = self.healer.heal(locator, page_source, str(exception))

        if healing_result and healing_result.success:
            try:
                # 使用修复后的XPath重新查找
                healed_element = driver.find_element(By.XPATH, healing_result.new_xpath)
                self.monitor.record_healing_success(locator, healing_result)
                return healed_element
            except Exception as e:
                self.monitor.record_healing_failure(locator, healing_result, f"新定位器无效: {str(e)}")

        return None

    def _patch_action_methods(self, driver):
        """拦截元素操作方法"""
        action_methods = ['click', 'send_keys', 'clear', 'submit', 'get_attribute']

        for method_name in action_methods:
            original = getattr(WebElement, method_name, None)
            if original:
                self.original_methods[f"webelement_{method_name}"] = original
                patched = self._create_action_wrapper(original, method_name)
                setattr(WebElement, method_name, patched)

    def _create_action_wrapper(self, original_method, method_name):
        """创建操作方法的包装器"""

        @wraps(original_method)
        def wrapper(element_self, *args, **kwargs):
            try:
                # 记录操作尝试
                element_id = id(element_self)
                self.monitor.record_action_attempt(element_id, method_name, args, kwargs)

                # 执行原始操作
                result = original_method(element_self, *args, **kwargs)

                # 记录操作成功
                self.monitor.record_action_success(element_id, method_name, args, kwargs, result)
                return result

            except StaleElementReferenceException as e:
                # 记录陈旧元素异常
                self.monitor.record_stale_element(element_id, method_name, e)

                # 如果启用自动修复，尝试重新查找元素
                if self.monitor.auto_heal:
                    healed_element = self._attempt_element_recovery(element_self, method_name, args, kwargs, e)
                    if healed_element:
                        # 在修复的元素上重试操作
                        return getattr(healed_element, method_name)(*args, **kwargs)

                # 重新抛出原始异常
                raise

        return wrapper

    def _attempt_element_recovery(self, stale_element, method_name, args, kwargs, exception):
        """尝试恢复陈旧的元素"""
        # 获取元素的原始定位信息
        element_info = self.monitor.get_element_info(id(stale_element))
        if not element_info:
            return None

        # 获取当前页面源码
        driver = self.monitor.get_current_driver()
        page_source = driver.page_source

        # 尝试自愈
        healing_result = self.healer.heal(
            element_info['locator'],
            page_source,
            f"Stale element: {str(exception)}"
        )

        if healing_result and healing_result.success:
            try:
                new_element = driver.find_element(By.XPATH, healing_result.new_xpath)
                self.monitor.record_healing_success(element_info['locator'], healing_result)
                return new_element
            except Exception:
                self.monitor.record_healing_failure(
                    element_info['locator'],
                    healing_result,
                    "新定位器无效"
                )

        return None