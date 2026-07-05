# headling

一个基于 **experta 专家系统**的 Selenium 自愈框架，能够在页面结构变化导致元素定位失败时，自动推理并验证新的 XPath，从而让自动化测试脚本具备自我修复能力。

## 特性

- **自动快照注册** — `find_element` 成功后自动保存元素快照到注册表
- **12 条自愈推理规则** — 按优先级依次尝试，涵盖多属性精确匹配、模糊匹配、结构深度过滤等策略
- **上下文感知** — 结合当前页面 DOM 上下文（表单ID、兄弟文本、同标签数量等）进行推理
- **Selenium 透明拦截** — 通过上下文管理器包装 driver，代码无需修改
- **持久化存储** — 快照自动保存为 HMAC 签名 JSON，重启后可恢复
- **线程安全** — 注册表和日志均支持多线程并发

## 架构

```
driver (Selenium)
    │
    ▼
SeleniumInterceptor          ← 拦截 find_element / find_elements
    │
    ├──▶ ElementRegistry     ← 全局单例，存储元素快照
    │
    ├──▶ Monitor            ← 记录查找成功/失败/自愈事件
    │
    └──▶ HealingEngine       ← 专家系统，按 12 条规则推理新 XPath
            │
            ▼
        WrappedElement       ← 返回给调用方的元素包装器
```

### 核心模块

| 模块 | 说明 |
|------|------|
| `healing_engine.py` | 专家系统核心，12 条推理规则（R001 ~ R012） |
| `selenium_interceptor.py` | Selenium 拦截器（上下文管理器） |
| `element_registry.py` | 线程安全全局元素快照注册表 |
| `element_wrapper.py` | 元素包装器，拦截操作并记录事件 |
| `web_element_data.py` | 元素快照数据结构 |
| `secure_pickle.py` | HMAC 签名 JSON 持久化 |
| `dom_parser.py` | 页面 DOM 上下文解析 |

### 自愈推理规则优先级

| 规则 | 描述 | 优先级 |
|------|------|--------|
| R001 | 精确多属性匹配（>=2 个高权重属性） | 1 |
| R002 | 单属性 + 文本内容匹配 | 2 |
| R003 | 父级上下文 + 属性匹配 | 3 |
| R004 | 相对位置索引匹配 | 4 |
| R005 | 邻近文本锚点匹配 | 5 |
| R006 | 表单序列匹配 | 6 |
| R007 | 模糊属性部分匹配 | 7 |
| R008 | 组合类名匹配 | 8 |
| R009 | 角色语义匹配（role 属性） | 9 |
| R010 | 结构深度过滤匹配 | 10 |
| R011 | 类型分组匹配 | 11 |
| R012 | 兜底策略 | 12 |

## 安装

```bash
pip install -r requirements.txt
```

主要依赖：
- `selenium >= 4.35`
- `experta >= 1.9`

> 需要预先准备好 ChromeDriver 并配置到 PATH 中，或在代码中指定 `Service(executable_path="...")`。

## 快速开始

```python
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from headling import SeleniumInterceptor, Monitor, HealingEngine

# 1. 初始化浏览器
service = Service(executable_path="./selenium_driver/chromedriver.exe")
driver = Chrome(service=service)

# 2. 用拦截器包装 driver
with SeleniumInterceptor(
    driver,
    monitor=Monitor(),
    healer=HealingEngine(),
    auto_heal=True,
    persist_file="elements.json"      # 可选：快照持久化路径
) as d:
    d.get("https://example.com")

    # 3. 正常使用 Selenium，拦截器自动工作
    elem = d.find_element(By.ID, "chat-textarea")
    elem.send_keys("hello")

    # 页面变化后，元素定位可能自动修复
    btn = d.find_element(By.CSS_SELECTOR, "#chat-submit-button")
    btn.click()

# 4. 退出时打印运行报告
print(d.monitor.report())
```

## 高级用法

### 直接使用注册表

```python
from headling import ElementRegistry, LocatorKey

registry = ElementRegistry.get_instance()

# 注册快照
registry.register((By.ID, "kw"), element_data)

# 查询快照
snapshot = registry.get((By.ID, "kw"))
```

### 单独使用自愈引擎（无需 Selenium）

```python
from headling import HealingEngine
from headling.models import WebElementData

engine = HealingEngine()
result = engine.run_healing(snapshot, page_source="<html>...</html>")
# result -> {"xpath": "...", "rule_id": "R001", "priority": 1} | None
```

### 自定义日志

```python
from utils.logutil import get_logger

logger = get_logger(name="myapp", level="INFO", use_console=True)
```

## 快照持久化

`persist_file` 参数指定快照文件的保存路径：

- **启动时** — 从 JSON 文件加载历史快照到注册表（与内存合并，不覆盖已有条目）
- **退出时** — 将注册表全量保存为 HMAC 签名 JSON

密钥文件自动管理（`persist_file.key`），无需手动指定。

## 运行演示

```bash
python healing.py
```

演示流程：
1. 初始化 Chrome 浏览器
2. 激活 SeleniumInterceptor
3. 执行多次 `find_element`（自动注册快照）
4. 演示元素操作拦截
5. 打印监控报告
6. 关闭浏览器

## 项目结构

```
headling/
├── __init__.py              ← 包入口，打印 Logo，导出公共 API
├── healing_engine.py        ← 专家系统核心（12 条规则）
├── selenium_interceptor.py   ← Selenium 拦截器
├── element_wrapper.py       ← 元素操作拦截包装器
├── element_registry.py      ← 全局注册表（单例）
├── web_element_data.py      ← 元素快照数据模型
├── dom_parser.py            ← DOM 上下文解析
├── facts.py                 ← 专家系统事实类型定义
├── monitor.py               ← 运行监控器
└── security/
    └── secure_pickle.py     ← HMAC 签名持久化

utils/
├── logutil/                 ← 日志工具
└── configutil/             ← 配置工具

healing.py                   ← 演示脚本
```

## License

Private - FUHAO
