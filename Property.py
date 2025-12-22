from selenium.webdriver.remote.webelement import WebElement
from typing import Dict, List, Optional, Union


class WebElementData:
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
            xpath: str = "",
            attributes: Dict[str, str] = None
    ):
        """
        通用网页元素数据容器
        参数:
            tag: 元素标签名 (如 'div', 'a', 'img')
            element_id: 元素的id属性
            classes: 元素的class列表
            text: 元素可见文本
            href: 链接地址 (适用于<a>标签)
            src: 资源地址 (适用于<img>, <script>等标签)
            name: 元素的name属性
            value: 元素的value属性 (适用于input等表单元素)
            xpath: 元素的绝对XPath路径
            attributes: 其他HTML属性的字典
        """
        self.tag = tag
        self.element_id = element_id
        self.classes = classes or []
        self.text = text
        self.href = href
        self.src = src
        self.name = name
        self.value = value
        self.xpath = xpath
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
            f"  XPath: {self.xpath}" if self.xpath else None,
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
            'xpath': self.xpath,
            'attributes': self.attributes
        }

    @classmethod
    def from_selenium_element(
            cls,
            element: WebElement,
            include_attributes: bool = True,
            custom_attributes: List[str] = None
    ) -> 'WebElementData':
        """
        从Selenium WebElement创建实例

        参数:
            element: Selenium WebElement对象
            include_attributes: 是否包含所有HTML属性
            custom_attributes: 要包含的特定属性列表

        返回:
            WebElementData实例
        """
        # 获取基本属性
        classes = element.get_attribute('class')

        # 获取绝对XPath路径
        xpath = cls._get_absolute_xpath(element)

        # 创建实例
        instance = cls(
            tag=element.tag_name,
            element_id=element.get_attribute('id'),
            classes=classes.split() if classes else [],
            text=element.text,
            href=element.get_attribute('href'),
            src=element.get_attribute('src'),
            name=element.get_attribute('name'),
            value=element.get_attribute('value'),
            xpath=xpath
        )

        # 获取其他属性
        if include_attributes or custom_attributes:
            if custom_attributes:
                # 获取指定属性
                for attr in custom_attributes:
                    attr_value = element.get_attribute(attr)
                    if attr_value:
                        instance.attributes[attr] = attr_value
            else:
                # 获取所有属性（通过JavaScript）
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

    @staticmethod
    def _get_absolute_xpath(element: WebElement) -> str:
        """
        计算元素的绝对 XPath 路径

        参数:
            element: Selenium WebElement 对象

        返回:
            绝对 XPath 字符串
        """
        try:
            xpath = element.parent.execute_script("""
                function getXPath(element) {
                    if (element.id !== '')
                        return "//*[@id='" + element.id + "']";

                    if (element === document.body)
                        return "//" + element.tagName.toLowerCase();

                    var ix = 0;
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element)
                            return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        if (sibling.nodeType === 1 && sibling.tagName.toLowerCase() === element.tagName.toLowerCase())
                            ix++;
                    }
                }
                return getXPath(arguments[0]);
            """, element)
            return xpath if xpath else ""
        except Exception:
            # 如果 JavaScript 执行失败，返回空字符串
            return ""

    def get_attribute(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """
        获取属性值，支持直接属性和自定义属性

        参数:
            name: 属性名称 (如 'id', 'class', 'data-custom')
            default: 未找到属性时的默认值

        返回:
            属性值字符串或默认值
        """
        # 检查直接属性
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

        # 检查自定义属性
        return self.attributes.get(name, default)