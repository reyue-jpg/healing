import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from typing import Dict, List, Optional, Union, Iterable, Iterator


class WebElementData:
    """通用网页元素数据容器"""

    def __init__(
            self,
            tag: str = "",
            element_id: str = "",
            classes: List[str] = None,
            text: str = "",
            href: str = "",
            src: str = "",
            name: str = "",
            value: str = "",
            attributes: Dict[str, str] = None
    ):
        self.tag = tag
        self.element_id = element_id
        self.classes = classes or []
        self.text = text
        self.href = href
        self.src = src
        self.name = name
        self.value = value
        self.attributes = attributes or {}

    def __str__(self) -> str:
        """可视化输出元素信息"""
        class_str = ' '.join(self.classes)
        info = [
            f"<{self.tag}{self._id_str()}{self._class_str()}>",
            f"  Text: {self.text}" if self.text else None,
            f"  Href: {self.href}" if self.href else None,
            f"  Src: {self.src}" if self.src else None,
            f"  Name: {self.name}" if self.name else None,
            f"  Value: {self.value}" if self.value else None,
            f"  Attributes: {self.attributes}" if self.attributes else None
        ]
        return '\n'.join(filter(None, info))

    def _id_str(self) -> str:
        return f" id='{self.element_id}'" if self.element_id else ""

    def _class_str(self) -> str:
        return f" class='{' '.join(self.classes)}'" if self.classes else ""

    def to_dict(self) -> Dict[str, Union[str, List[str], Dict]]:
        """转换为字典格式"""
        return {
            'tag': self.tag,
            'id': self.element_id,
            'classes': self.classes,
            'text': self.text,
            'href': self.href,
            'src': self.src,
            'name': self.name,
            'value': self.value,
            'attributes': self.attributes
        }

    def get_attribute(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """获取属性值，支持直接属性和自定义属性"""
        direct_attributes = {
            'id': self.element_id,
            'class': ' '.join(self.classes),
            'href': self.href,
            'src': self.src,
            'name': self.name,
            'value': self.value,
            'text': self.text
        }

        if name in direct_attributes:
            return direct_attributes[name] or default

        return self.attributes.get(name, default)

    @classmethod
    def from_selenium_element(
            cls,
            element: WebElement,
            include_attributes: bool = True,
            custom_attributes: List[str] = None
    ) -> 'WebElementData':
        """从Selenium WebElement创建实例"""
        classes = element.get_attribute('class')

        instance = cls(
            tag=element.tag_name,
            element_id=element.get_attribute('id'),
            classes=classes.split() if classes else [],
            text=element.text,
            href=element.get_attribute('href'),
            src=element.get_attribute('src'),
            name=element.get_attribute('name'),
            value=element.get_attribute('value')
        )

        # 获取其他属性
        if include_attributes or custom_attributes:
            if custom_attributes:
                for attr in custom_attributes:
                    attr_value = element.get_attribute(attr)
                    if attr_value:
                        instance.attributes[attr] = attr_value
            else:
                # 使用JavaScript获取所有属性
                all_attrs = element.parent.execute_script(
                    'var items = {}; '
                    'for (index = 0; index < arguments[0].attributes.length; ++index) { ' 
                    '  items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value '
                    '} '
                    'return items;',
                    element
                )
                instance.attributes = all_attrs

        return instance


class WebElementCollection:
    """管理多个WebElementData的集合容器"""

    def __init__(self, elements: Optional[Iterable[WebElementData]] = None):
        """
        初始化元素集合

        参数:
            elements: WebElementData对象列表 (可选)
        """
        self._elements: List[WebElementData] = list(elements) if elements else []

    def __len__(self) -> int:
        """获取元素数量"""
        return len(self._elements)

    def __getitem__(self, index: Union[int, slice]) -> Union['WebElementData', 'WebElementCollection']:
        """索引访问元素"""
        if isinstance(index, slice):
            return WebElementCollection(self._elements[index])
        return self._elements[index]

    def __iter__(self) -> Iterator[WebElementData]:
        """迭代元素"""
        return iter(self._elements)

    def __str__(self) -> str:
        """集合的字符串表示"""
        return f"WebElementCollection with {len(self)} elements"

    def __contains__(self, element: WebElementData) -> bool:
        """检查元素是否在集合中"""
        return element in self._elements

    def append(self, element: WebElementData):
        """添加单个元素到集合"""
        self._elements.append(element)

    def extend(self, elements: Iterable[WebElementData]):
        """添加多个元素到集合"""
        self._elements.extend(elements)

    def add_from_selenium_list(
            self,
            selenium_elements: List[WebElement],
            include_attributes: bool = True,
            custom_attributes: List[str] = None
    ):
        """从Selenium元素列表添加多个元素"""
        self._elements.extend(
            WebElementData.from_selenium_element(
                elem,
                include_attributes,
                custom_attributes
            )
            for elem in selenium_elements
        )

    def filter(self, condition) -> 'WebElementCollection':
        """
        根据条件过滤元素

        参数:
            condition: 函数，接受WebElementData对象返回布尔值

        返回:
            新的过滤后的集合
        """
        return WebElementCollection(filter(condition, self._elements))

    def filter_by_class(self, class_name: str) -> 'WebElementCollection':
        """按class名称过滤元素"""
        return self.filter(lambda e: class_name in e.classes)

    def filter_by_tag(self, tag_name: str) -> 'WebElementCollection':
        """按标签名过滤元素"""
        return self.filter(lambda e: e.tag.lower() == tag_name.lower())

    def filter_by_attribute(self, attr_name: str, attr_value: Optional[str] = None) -> 'WebElementCollection':
        """按属性过滤元素"""
        if attr_value is not None:
            return self.filter(lambda e: e.get_attribute(attr_name) == attr_value)
        return self.filter(lambda e: e.get_attribute(attr_name) is not None)

    def get_by_index(self, index: int) -> Optional[WebElementData]:
        """通过索引获取元素"""
        try:
            return self._elements[index]
        except IndexError:
            return None

    def get_by_id(self, element_id: str) -> Optional[WebElementData]:
        """通过ID获取元素"""
        for element in self._elements:
            if element.element_id == element_id:
                return element
        return None

    def get_by_text(self, text: str, exact_match: bool = True) -> Optional[WebElementData]:
        """通过文本内容获取元素"""
        for element in self._elements:
            if exact_match:
                if element.text == text:
                    return element
            else:
                if text in element.text:
                    return element
        return None

    def to_list(self) -> List[WebElementData]:
        """转换为元素列表"""
        return self._elements.copy()

    def to_dict_list(self) -> List[Dict]:
        """转换为字典列表"""
        return [element.to_dict() for element in self._elements]

    def sort_by(self, key_func, reverse: bool = False):
        """根据指定键函数对元素排序"""
        self._elements.sort(key=key_func, reverse=reverse)

    def sort_by_text(self, reverse: bool = False):
        """按文本内容排序"""
        self.sort_by(lambda e: e.text, reverse)

    def sort_by_attribute(self, attribute: str, reverse: bool = False):
        """按指定属性排序"""
        self.sort_by(lambda e: e.get_attribute(attribute, ""), reverse)

    @classmethod
    def from_selenium_list(
            cls,
            selenium_elements: List[WebElement],
            include_attributes: bool = True,
            custom_attributes: List[str] = None
    ) -> 'WebElementCollection':
        """
        从Selenium元素列表创建集合

        参数:
            selenium_elements: Selenium WebElement对象列表
            include_attributes: 是否包含所有属性
            custom_attributes: 要包含的特定属性列表

        返回:
            WebElementCollection实例
        """
        collection = cls()
        collection.add_from_selenium_list(selenium_elements, include_attributes, custom_attributes)
        return collection


class BuildLogger:
    _instance = {}

    def __init__(
            self,
            logdir: Optional[str] = None,
            log_name: Optional[str] = None,
            log_level: int = logging.DEBUG,
            max_bytes: int = 10 * 1024 * 1024,
            backup_count: int = 3,
            use_console: bool = False,
            use_timed_rotating: bool = False,
            timed_when: str = "midnight",
            timed_interval: int = 1,
            timed_backup_count: int = 7
    ):

        self.logdir = logdir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        self.log_name = log_name or datetime.today().strftime('%Y%m%d') + '.log'
        self.log_level = log_level
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.logger = None

        self._ensure_log_directory()
        self._init_logger(
            use_console=use_console,
            use_timed_rotating=use_timed_rotating,
            timed_when=timed_when,
            timed_interval=timed_interval,
            timed_back_count=timed_backup_count
        )

    def _init_logger(self, **kwargs):
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )

        self.logger = logging.getLogger(self.log_name)
        self.logger.setLevel(self.log_level)

        print(self.logger.handlers)
        if not self.logger.handlers:
            rotating_handler = RotatingFileHandler(
                filename=os.path.join(self.logdir, self.log_name),
                maxBytes=self.max_bytes,
                backupCount=self.backup_count
            )
            rotating_handler.setFormatter(formatter)
            rotating_handler.setLevel(self.log_level)
            self.logger.addHandler(rotating_handler)

            if kwargs.get('use_console'):
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                console_handler.setLevel(self.log_level)
                self.logger.addHandler(console_handler)

            if kwargs.get('use_timed_rotating'):
                timed_handler = TimedRotatingFileHandler(
                    filename=os.path.join(self.logdir, self.log_name),
                    when=kwargs['timed_when'],
                    interval=kwargs['timed_interval'],
                    backupCount=kwargs['timed_backup_count']
                )
                timed_handler.setFormatter(formatter)
                timed_handler.setLevel(self.log_level)
                self.logger.addHandler(timed_handler)

    def _ensure_log_directory(self):
        os.makedirs(self.logdir, exist_ok=True)

    def add_custom_handler(self, handler):
        if isinstance(handler, logging.Handler):
            raise TypeError("The handler must be a subclass of logging.Handler")
        self.logger.addHandler(handler)

    def get_logger(self) -> logging.Logger:
        return self.logger

class Tlogger(BuildLogger):
    _instance = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def get_T_default_logger(cls, **kwargs) -> logging.Logger:
        instance_key = str(kwargs)
        print(instance_key)

        if instance_key not in cls._instance:
            cls._instance[instance_key] = cls(**kwargs)

        return cls._instance[instance_key].logger

class WebTest:
    def web_test(self):
        driver = webdriver.Edge()
        driver.get("http://www.baidu.com")
        time.sleep(5)
        web_element = driver.find_element(By.XPATH, "//div[@class='san-card']")
        link = WebElementData.from_selenium_element(web_element)
        print(link)


if __name__ == '__main__':
    # logger = Buildlogger(use_console=True)
    # tlogger = logger.get_logger()
    # tlogger.error("hi")

    # logger = Buildlogger.get_default_logger(use_console=True)
    # logger.info("hi")

    logger = Tlogger.get_T_default_logger(use_console=True)
    logger.info("hi")
    w = WebTest()
    w.web_test()