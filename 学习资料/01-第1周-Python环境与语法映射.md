# 第 1 周：Python 环境 + 语法映射

> 阶段一 · 第 1 周。目标：不追求精通，而是建立「Kotlin → Python」的翻译能力，能顺畅读写 Agent 生态代码。

## 学习目标

1. 用 `uv` 建好可复现的 Python 开发环境
2. 掌握与 Kotlin 高频对应的核心语法：变量、函数、控制流、四大容器
3. 亲手踩一次「可变默认参数」的坑并解释原因
4. 产出：命令行 TODO 工具（JSON 持久化）

## 1. 环境搭建（对照安卓世界的角色）

| 安卓世界 | Python 世界 | 说明 |
| --- | --- | --- |
| JDK | Python 解释器 | 装 3.11+ |
| Gradle + version catalog | **uv** | 管虚拟环境、依赖、锁版本 |
| Maven Central | PyPI | 包仓库 |
| `build.gradle.kts` | `pyproject.toml` | 项目清单文件 |
| `compileOnly/prodImplementation` | 依赖分组 | 基本只有一种依赖 |

### 安装步骤（Windows / PowerShell）

```powershell
# 1. 安装 uv（官方安装脚本）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. 验证
uv --version

# 3. 创建项目
mkdir agent-learning
cd agent-learning
uv init week01
cd week01

# 4. 添加依赖（示例）
uv add httpx
# 运行脚本
uv run python main.py
```

### 编辑器

VS Code + 「Python」+「Pylance」插件即可；想要开箱即用的重构体验就装 PyCharm Community（免费）。

### git 仓库

```powershell
cd agent-learning
git init
# .gitignore 至少包含：
#   .env
#   __pycache__/
#   .venv/
```

按周建目录：`week01/`、`week02/`……所有代码提交进去。

## 2. 语法映射速查表（本资料核心）

### 2.1 变量与类型

```kotlin
// Kotlin：静态类型
val name: String = "Tom"
var age: Int = 25
val maybe: String? = null
```

```python
# Python：动态类型，标注只是提示、运行时不强制
name: str = "Tom"       # name = "Tom" 也行
age = 25                # 数字会自动扩为任意精度，无 Int 溢出
maybe: str | None = None  # None 对应 Kotlin 的 null；没有 ? 语法
```

要点：

- **动态类型**：同一个变量可以重新赋值为任何类型。标注 `str` 不写也不会报错，但 Agent 生态代码全部带标注，务必养成写标注的习惯。
- `None` 就是 Kotlin 的 `null`，判空用 `if x is None`，对应 `if (x == null)`。
- 数字只有 `int`/`float`/`bool`，没有 `Long/Short/Byte` 之分。

### 2.2 函数

```kotlin
// Kotlin
fun greet(name: String, greeting: String = "Hello") = "$greeting, $name"
greet("Tom", greeting = "Hi")   // 命名参数
```

```python
# Python
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}"

greet("Tom", greeting="Hi")     # 关键字参数，与 Kotlin 命名参数几乎一样
```

新增概念 `*args / **kwargs`（Kotlin 的 `vararg` 高配版）：

```python
def log(level: str, *tags: str, **extras: str) -> None:
    # tags 是元组 ("net", "db")，extras 是字典 {"user": "tom"}
    print(level, tags, extras)

log("INFO", "net", "db", user="tom")
```

Agent 框架大量用 `**kwargs` 做参数透传，看到不要慌：**它是「把剩余关键字参数收进一个 dict」**。

### 2.3 控制流

```python
nums = [1, 2, 3, 4]
for i, n in enumerate(nums):      # 同时拿下标和值
    if n > 2:
        print(f"index={i}, value={n}")
else:
    pass  # for-else：循环正常结束（没 break）才执行，了解即可

while True:
    cmd = input("> ")
    if cmd == "exit":
        break
```

与 Kotlin 最大的差异：**没有花括号，靠缩进（4 空格）**；没有三元运算符，用 `x if cond else y`。

### 2.4 核心数据结构（一天掌握，反复用）

```python
lst: list[str] = ["a", "b"]        # ≈ List<String>，可变、有序
tup: tuple[str, int] = ("a", 1)    # ≈ Pair<String, Int> 的多元素版，不可变
dic: dict[str, int] = {"x": 1}     # ≈ Map<String, Int>，3.7+ 保证插入有序
st: set[str] = {"a", "b"}          # ≈ Set<String>，自动去重

lst.append("c")            # ≈ add
lst[0]                     # 取值；越界抛 IndexError（不是 null）
lst[-1]                    # 最后一个，负索引是特色
"b" in lst                 # ≈ contains
dic.get("y", 0)            # ≈ getOrDefault
dic["y"] = 2               # ≈ put
dic.keys() / .values() / .items()   # items() ≈ entries
del dic["y"]               # ≈ remove
lst2 = lst.copy()          # 浅拷贝
```

注意：Kotlin 的 `val` 是「引用不可变」，Python 没有对应物——所有变量都可重新绑定，靠纪律不靠语法。

### 2.5 列表推导式（必须练到肌肉记忆）

```python
nums = [-2, -1, 0, 1, 2, 3]

doubled = [x * 2 for x in nums]                  # ≈ map
positives = [x for x in nums if x > 0]           # ≈ filter
both = [x * 2 for x in nums if x > 0]            # ≈ filter + map
pairs = {w: len(w) for w in ["ab", "cde"]}       # dict 推导式
flat = [c for w in ["ab", "c"] for c in w]       # 嵌套（对应 flatMap）
gen = (x * 2 for x in nums)                      # 惰性版 ≈ Sequence
```

对照 Kotlin：`nums.filter { it > 0 }.map { it * 2 }`。推导式从左到右读就是从外到内的循环。

### 2.6 字符串：f-string

```python
name, score = "Tom", 97.5
print(f"{name} 得分 {score:.1f}")       # ≈ Kotlin "$name 得分 ${"%.1f".format(score)}"
print(f"{score=}")                     # 调试神器：输出 score=97.5
```

## 3. 本周陷阱精讲：可变默认参数

```python
def add_item(item, items=[]):        # 危险！
    items.append(item)
    return items

add_item("a")   # ["a"]
add_item("b")   # ["a", "b"]  ← 惊讶：不是 ["b"]
```

**原因**：默认值在**函数定义时求值一次**，之后所有调用共享同一个 list 对象（类似 Kotlin 里把一个单例 mutable list 作为默认值，但没有语法保护）。

**正确写法**：

```python
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

这个坑在 LLM 的 `messages` 参数上非常常见，很多教程代码都带着它，你要能一眼识别。

## 4. 本周项目实战：命令行 TODO 工具

需求：`uv run python todo.py add "买牛奶"` / `list` / `done 1` / `del 2`，数据存 `todo.json`。

`week01/todo.py`：

```python
"""命令行 TODO 工具：数据用 JSON 文件持久化。"""
import json
import sys
from pathlib import Path

STORE = Path(__file__).parent / "todo.json"


def load() -> list[dict]:
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text(encoding="utf-8"))


def save(items: list[dict]) -> None:
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add(text: str) -> None:
    items = load()
    items.append({"id": max((i["id"] for i in items), default=0) + 1, "text": text, "done": False})
    save(items)
    print(f"已添加 #{items[-1]['id']}")


def show() -> None:
    items = load()
    if not items:
        print("(空)")
        return
    for it in items:
        mark = "x" if it["done"] else " "
        print(f"[{mark}] #{it['id']} {it['text']}")


def set_done(item_id: int, done: bool) -> None:
    items = load()
    for it in items:
        if it["id"] == item_id:
            it["done"] = done
            save(items)
            return
    print(f"没有 #{item_id}")


def delete(item_id: int) -> None:
    items = [it for it in load() if it["id"] != item_id]
    save(items)


def main() -> None:
    if len(sys.argv) < 2:
        show()
        return
    cmd, *args = sys.argv[1:]
    if cmd == "add" and args:
        add(" ".join(args))
    elif cmd == "list":
        show()
    elif cmd == "done" and args:
        set_done(int(args[0]), True)
    elif cmd == "del" and args:
        delete(int(args[0]))
    else:
        print("用法: todo.py add <内容> | list | done <id> | del <id>")


if __name__ == "__main__":
    main()
```

自己实现时先只看需求写，卡住再看这份骨架。练习点：argparse 解析、`pathlib` 读写文件、推导式过滤。

## 5. 验收自测（对应计划验收标准）

- [ ] **不查教程**写出 TODO 工具（增/删/列 + JSON 持久化）
- [ ] 能口述可变默认参数为什么危险，并给出两种修法（`None` 哨兵 / `tuple` 默认）
- [ ] 代码已提交 git，`week01` 目录下可 `uv run` 复现

自测题（口头回答）：
1. `list` 和 `tuple` 的核心区别？什么时候用 tuple？
2. `dic.get("k")` 和 `dic["k"]` 在 key 不存在时的行为差异？
3. 把 `[x for x in nums if x > 0]` 翻译回 Kotlin 链式调用。

## 6. 衔接第 2 周

第 1 周的 TODO 工具里，TODO 条目是裸 dict——没有类型保护、没有校验。第 2 周将用 `dataclass` + **pydantic** 把它升级成强类型、带校验的模型，这正是所有 Agent 框架定义工具参数（schema）的方式。第 2 周见。
