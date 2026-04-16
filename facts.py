from experta import Fact

class ElementFact(Fact):
    """元素特征事实"""
    pass

class StrategyFact(Fact):
    """策略生成事实"""
    pass

class ContextFact(Fact):
    """上下文事实"""
    pass

class ElementFeaturesFact(Fact):
    """详细的元素特征事实"""
    tag: str
    stable_attributes: dict
    text_content: str
    position_score: float
    structural_depth: int
    has_unique_parent: bool
    has_stable_siblings: bool
    is_form_control: bool
    page_type: str = "unknown"

class DOMContextFact(Fact):
    """DOM上下文事实"""
    dom_size: int
    average_depth: float
    form_count: int
    dynamic_content_ratio: float


from experta import *

class NodeFact(Fact):
    """代表一个DOM节点的事实"""
    tag: str
    index: int
    parent_index: int

class XPathFact(Fact):
    """代表一个XPath表达式"""
    xpath: str

class XPathEngine(KnowledgeEngine):
    @DefFacts()
    def _initial_facts(self):
        # 假设有一组初始文档节点
        yield NodeFact(tag="div", index=0, parent_index=-1)
        yield NodeFact(tag="p", index=1, parent_index=0)
        yield NodeFact(tag="span", index=2, parent_index=0)
        yield NodeFact(tag="a", index=3, parent_index=0)

    @Rule(NodeFact(tag=MATCH.tag, index=MATCH.index, parent_index=MATCH.parent_index),
          NOT(XPathFact(xpath=W())))
    def generate_xpath(self, tag, index, parent_index):
        # 生成当前节点的路径表达式
        xpath = f"//{tag}[{index + 1}]"
        self.declare(XPathFact(xpath=xpath))
        print(f"Generated XPath for node: {xpath}")

    @Rule(XPathFact(xpath=MATCH.xpath),
          NodeFact(tag=MATCH.tag, index=MATCH.index, parent_index=MATCH.parent_index))
    def find_adjacent_nodes(self, xpath, tag, index, parent_index):
        # 找到当前节点的相邻节点
        adjacent_nodes = []
        for node in self.facts:
            if isinstance(node, NodeFact) and node.parent_index == parent_index and node.index != index:
                adjacent_nodes.append(node)

        if adjacent_nodes:
            for adjacent_node in adjacent_nodes:
                adjacent_xpath = f"//{adjacent_node.tag}[{adjacent_node.index + 1}]"
                print(f"Adjacent node XPath: {adjacent_xpath}")

engine = XPathEngine()
engine.reset()


engine.run()
