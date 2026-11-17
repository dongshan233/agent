# 第 2 周：函数进阶 + OOP + 类型标注 + pydantic

> 阶段一 · 第 2 周。本周重点是 **pydantic**——Function Calling 的 JSON schema 和几乎所有 Agent 框架的地基。

## 学习目标

1. 掌握类、`dataclass`、模块与 `import` 机制
2. 熟练使用 `typing`：`Optional`、`Literal`、`TypedDict`、泛型标注
3. 用 pydantic 定义带嵌套、默认值、校验的模型
4. 产出：「安卓设备信息」校验程序

## 1. 类与对象（对照 Kotlin）

### 1.1 基本类

```kotlin
// Kotlin
class Person(val name: String, var age: Int) {
    fun greet() = "I'm $name"
}
```

```python
class Person:
    def __init__(self, name: str, age: int):   # ≈ 主构造器
        self.name = name                        # 必须挂到 self 上才是字段
        self.age = age

    def greet(self) -> str:                     # 第一个参数永远是 self ≈ this
        return f"I'm {self.name}"

p = Person("Tom", 25)      # 不需要 new
print(p.greet())           # 调用时不用传 self
```

要点：

- **没有真正的私有成员**：`_name` 是约定（别碰），`__name` 触发名称改写（了解即可），主要靠纪律。
- 类属性 vs 实例属性：直接写在 class 体内的变量是类属性（≈ Kotlin companion object 的 field）。

### 1.2 dataclass（对应 Kotlin data class）

```python
from dataclasses import dataclass, field

@dataclass
class Device:
    model: str
    version: str = "14"          # 默认值
    apps: list[str] = field(default_factory=list)   # 可变类型默认值必须用 factory（呼应第1周的坑）

d = Device("Pixel 8")
print(d)          # 自动生成 __repr__：Device(model='Pixel 8', version='14', apps=[])
print(d == Device("Pixel 8"))   # 自动生成 __eq__，按字段比较
```

`dataclass` 只是「生成样板方法」的语法糖，**不做任何校验**——传 `"model": 123` 不会报错。这就是 pydantic 存在的理由。

## 2. 模块与包

```python
# 文件即模块，目录即包
from agent.tools import calc        # ≈ import agent.tools.calc
import httpx as hx                  # 别名

# 每个可执行脚本保留这个入口（≈ Kotlin 的 main）：
if __name__ == "__main__":
    main()
```

- 被 `import` 的文件不会执行 `if __name__ == "__main__"` 里的代码——这句判断的意思是「只有直接运行我时才是 main」。测试代码、示例代码放这里。
- 项目内相对导入：同一个包内用 `from .utils import load`（≈ Kotlin 同 package 直接可见，Python 必须显式导入）。

## 3. 类型标注（Agent 代码的通行证）

Agent 框架源码满屏标注，本周把高频款全部过一遍：

```python
from typing import Annotated, Any, Literal, Optional, TypedDict

# Optional[X] ≈ X?；3.10+ 更推荐 X | None
def find(name: str) -> Optional[str]: ...

# Literal：枚举取值（schema 生成会用到它！）
Role = Literal["system", "user", "assistant", "tool"]

# TypedDict：给 dict 附加类型，运行时仍是普通 dict
class Message(TypedDict):
    role: str
    content: str

msg: Message = {"role": "user", "content": "hi"}

# Annotated：在类型上挂元数据——LangGraph 的核心写法
from operator import add
State = Annotated[list[str], add]   # 类型是 list[str]，元数据告诉框架"用 add 合并"

# 泛型容器
def first(items: list[str]) -> str | None: ...
def parse(raw: dict[str, Any]) -> Any: ...

# Callable ≈ 函数类型
from typing import Callable
Handler = Callable[[str], bool]     # ≈ (String) -> Boolean
```

**本周验收里那句 `Annotated[list, add_messages]` 现在就能看懂了**：`list` 是真实类型，第二个参数是给框架看的「合并策略」元数据，运行时 Python 完全忽略它。第 7 周 LangGraph 会大量使用。

## 4. 异常处理

```python
class ToolError(Exception):
    """自定义异常 ≈ Kotlin 自定义 Exception 类"""
    def __init__(self, tool: str, detail: str):
        super().__init__(f"[{tool}] {detail}")
        self.tool = tool

try:
    raise ToolError("weather", "API 超时")
except ToolError as e:              # ≈ catch (e: ToolError)
    print(f"捕获: {e}")
except (ValueError, KeyError):      # 多类型合并捕获
    print("参数错误")
else:
    print("没抛异常才执行")           # ≈ 无 try-with-resources 场景
finally:
    print("总是执行")
```

- Python 异常是** unchecked** 的，签名不声明、调用方不强制处理（和 Java/Kotlin checked exception 体系不同）。
- Agent 开发里最常用场景：包住工具执行，把异常**转成字符串返回给模型**而不是让进程崩（第 5 周会用到）。

## 5. pydantic（本周重中之重）

pydantic = **「dataclass + 运行时校验 + JSON 互转」**。安装：`uv add pydantic`。

### 5.1 定义模型与校验

```python
from pydantic import BaseModel, Field, field_validator

class App(BaseModel):
    name: str
    package: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")   # 正则校验

class Device(BaseModel):
    model: str
    os_version: str = Field(alias="osVersion", default="14")   # alias 对应 JSON 字段名
    ram_gb: int = Field(gt=0, le=64, description="内存大小(GB)")   # 约束 + schema 描述
    apps: list[App] = []                       # 嵌套模型，自动递归校验
    tags: set[str] = set()

    @field_validator("os_version")
    @classmethod
    def check_version(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("版本号必须是数字字符串")
        return v
```

### 5.2 解析与序列化（天天用的两个方法）

```python
raw = {"model": "Pixel 8", "osVersion": "14", "ram_gb": 8,
       "apps": [{"name": "微信", "package": "com.tencent.mm"}]}

device = Device.model_validate(raw)       # dict → 模型，校验失败抛 ValidationError
print(device.os_version)                  # "14"（alias 转成字段名）

json_str = device.model_dump_json(exclude={"tags"})   # 模型 → JSON 字符串
back = Device.model_validate_json(json_str)            # JSON 字符串 → 模型
as_dict = device.model_dump()                          # 模型 → dict
```

对照记忆：`model_validate` ≈ Gson/Moshi 的 `fromJson` + 强校验；`model_dump` ≈ `toJson`。

### 5.3 错误长什么样（故意传错看看）

```python
from pydantic import ValidationError

try:
    Device.model_validate({"model": "", "ram_gb": -1})
except ValidationError as e:
    print(e)   # 一次性列出所有错误：字段、原因、实际值
```

输出类似：

```
2 validation errors for Device
model
  String should have at least 1 character [type=string_too_short, ...]
ram_gb
  Input should be greater than 0 [type=greater_than, ...]
```

### 5.4 与 Agent 的关系（为什么要学它）

Agent 里给模型定义工具时，最终都要产出一份 **JSON Schema** 描述「参数名、类型、约束、说明」。pydantic 模型可以一键生成：

```python
print(Device.model_json_schema())   # 自动生成 JSON Schema！
```

第 5 周 Function Calling 里的 `parameters` 就是这个东西。**pydantic 模型 = 工具参数的定义方式**，这一条理解了，第 5 周就成功一半。

### 5.5 常用 Field 约束速查

| 写法 | 含义 |
| --- | --- |
| `Field(gt=0, le=100)` | 数值范围 |
| `Field(min_length=1, max_length=50)` | 字符串长度 |
| `Field(pattern=r"...")` | 正则 |
| `Field(default=..., description="...")` | 默认值 + 描述（schema 里会带） |
| `Field(alias="xxx")` | JSON 字段名映射 |
| `Optional[x] = None` | 可空 |

## 6. 本周项目实战：安卓设备信息校验

`week02/device_check.py`：

```python
"""从 JSON 加载设备信息并校验；故意传错类型观察报错。"""
import json
import sys
from pydantic import BaseModel, Field, ValidationError

class InstalledApp(BaseModel):
    name: str = Field(min_length=1)
    package: str = Field(pattern=r"^[a-z][\w]*(\.[\w]+)+$")
    version: str | None = None

class DeviceInfo(BaseModel):
    model: str = Field(min_length=1, examples=["Pixel 8"])
    os_version: str = Field(alias="osVersion", pattern=r"^\d+(\.\d+)*$")
    ram_gb: int = Field(gt=0, le=64)
    battery_pct: int = Field(default=100, ge=0, le=100)
    apps: list[InstalledApp] = []

SAMPLE = """
{"model": "Pixel 8", "osVersion": "14", "ram_gb": 8,
 "apps": [{"name": "微信", "package": "com.tencent.mm"},
          {"name": "Chrome", "package": "com.android.chrome", "version": "120"}]}
"""

def main() -> None:
    # 正常路径
    device = DeviceInfo.model_validate_json(SAMPLE)
    print(f"设备: {device.model} / Android {device.os_version} / {device.ram_gb}GB")
    print(f"应用({len(device.apps)}): " + ", ".join(a.name for a in device.apps))
    print("schema 片段:", DeviceInfo.model_json_schema()["properties"]["ram_gb"])

    # 错误路径：故意传错
    bad = '{"model": 123, "osVersion": "v14", "ram_gb": -8, "apps": [{"name": "", "package": "bad"}]}'
    try:
        DeviceInfo.model_validate_json(bad)
    except ValidationError as e:
        print("\n校验失败明细：")
        for err in e.errors():
            print(f"  {'.'.join(str(x) for x in err['loc'])}: {err['msg']} (type={err['type']})")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

练习任务（在骨架上扩展）：
1. 加字段 `screen_size_in: float`，约束 `4 < x < 10`
2. 写一个函数 `is_flagship(device) -> bool`（ram_gb >= 8 且 model 含 "Pro"），标注好类型
3. 把 `model_json_schema()` 完整打印出来，逐字段看懂它和 pydantic 定义的对应关系

## 7. 验收自测

- [ ] 能独立写出带嵌套模型、默认值、Field 校验、`field_validator` 的 pydantic 类
- [ ] 能解释 `dataclass` 和 pydantic `BaseModel` 的区别（样板生成 vs 运行时校验）
- [ ] 能用自己的话解释 `Annotated[list, add_messages]`：类型 + 合并策略元数据
- [ ] 故意传错类型的报错现象已观察并记录
- [ ] 代码提交 git

自测题：
1. `TypedDict` 和 `BaseModel` 都能描述结构，运行时差别是什么？
2. `Field(description=...)` 会出现在 `model_json_schema()` 里吗？为什么这对 Agent 很重要？
3. `model_validate` 和 `model_validate_json` 各自接收什么？

## 8. 衔接第 3 周

现在你会定义「数据模型」了。但 Agent 是要**干活**的：调 API、并发请求、跑测试。第 3 周讲 asyncio（对照 Kotlin 协程）、httpx（对照 Retrofit）和 pytest，学完你就有完整的 Python 工程能力。第 3 周见。
