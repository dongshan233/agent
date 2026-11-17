# 第 7 周：LangGraph 基础

> 阶段四 · 第 7 周。用 LangGraph 重构第 6 周的手写 Agent。**主资源：LangChain Academy 免费课（Introduction to LangGraph）+ docs.langchain.com。本资料负责对照你手写过的代码讲清楚每个 API。**

## 学习目标

1. 理解 StateGraph 三要素：State / Node / Edge
2. 掌握条件边与 `add_messages` 合并机制
3. 把第 6 周手写 Agent 重构为图
4. 能说出框架替你做了哪些事

## 1. 为什么需要框架（先看痛点）

第 6 周的 Agent 存在这些痛点：

| 手写版痛点 | 后果 |
| --- | --- |
| 状态就是一个 `history` list，散落在函数间 | 加功能要改多处 |
| 控制流埋在 for 循环里 | 想在「调模型」和「执行工具」之间插入别的步骤（如人工确认）必须改循环 |
| 无持久化 | 进程一死全部丢失 |
| 复杂 Agent（多分支、并行、子任务）循环写不动 | 代码迅速面条化 |

LangGraph 的答案：**把 Agent 显式建模为状态机**。状态（State）是共享数据，节点（Node）是修改状态的函数，边（Edge）是状态机流转。

对照安卓：**本质是页面导航图（Navigation Graph）**——目的地是节点，action 是边，conditional navigation 是条件边，savedStateHandle 是后面要学的 Checkpointer。这个类比贯穿本周。

## 2. 三要素详解

### 2.1 State：共享状态（TypedDict + Annotated）

```python
from typing import Annotated
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 第2周埋的伏笔，现在解释
```

- State 是一个 TypedDict：图运行期间所有节点共享的「内存」。
- `Annotated[list, add_messages]` 里的第二个参数是**归约函数（reducer）**：当一个节点返回新的 `messages` 值时，框架用 `add_messages([旧值], [新值])` 合并而不是覆盖。
- `add_messages` 的行为：按 id 追加新消息、更新同 id 消息——正好就是「往对话历史追加」的语义。第 4 周你手动 `history.append(...)` 的每一行，框架现在替你做了。

如果字段没有 reducer（如 `count: int`），节点返回新值就是**直接覆盖**。

### 2.2 Node：干活的函数

```python
# 节点签名固定：接收 state，返回「要更新的字段」
def call_model(state: AgentState) -> dict:
    reply = llm_call(state["messages"])        # 调模型（内部封 messages→API）
    return {"messages": [reply]}               # 只写增量！框架负责合并进 state

def execute_tools(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = [run_tool(tc) for tc in last.tool_calls]
    return {"messages": results}               # tool 消息，经 add_messages 追加
```

关键点：**节点返回增量，不是完整状态**。这像 Compose 的状态更新——你声明「变化」，框架负责应用。

### 2.3 Edge 与条件边

```python
from langgraph.graph import StateGraph, END

graph = StateGraph(AgentState)
graph.add_node("model", call_model)            # (节点名, 函数)
graph.add_node("tools", execute_tools)

graph.set_entry_point("model")                 # 起点
graph.add_edge("tools", "model")               # 固定边：tools 完必回 model

def route(state: AgentState) -> str:           # 条件边：决定下一步去哪
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"                          # 有工具调用 → 去工具节点
    return END                                  # 否则结束（≈ 第6周 finish_reason==stop 判断）

graph.add_conditional_edges("model", route, {"tools": "tools", END: END})
app = graph.compile()
```

完整数据流：

```
START → model ──有tool_calls──→ tools ──固定边──→ model
              └──无tool_calls──→ END
```

**这就是你第 6 周写的 while 循环**：`model→tools→model` 的固定边 + 条件边 = 循环；`END` = 循环退出。框架内帮你在跑同一个循环，只是控制流被声明式地画了出来。

注意：LangGraph 的循环有内置默认递归上限（默认 25 步），对应你手写的 MAX_TURNS 护栏，可用 `app.invoke(state, config={"recursion_limit": 10})` 调整。

## 3. 接入 LLM 与工具

有两种方式，学习期用第一种（看得见底层）：

```python
# 方式A：沿用你第 4~6 周的裸 httpx 封装（自己实现 llm_call / run_tool）
# 方式B：官方模型封装 + @tool 装饰器（生产常用，了解即可）
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """查询指定城市当前气温。"""          # docstring 自动变成工具描述+schema
    ...

llm = init_chat_model("openai:gpt-4o-mini").bind_tools([get_weather])
```

`@tool` 装饰器同样用类型标注 + docstring 生成 schema——和第 2 周 pydantic、第 5 周手写 schema 一脉相承。

## 4. 运行与观测

```python
state = app.invoke({"messages": [("user", "苏州今天多少度，比25度高几度")]})
print(state["messages"][-1].content)

# 流式观察每一步（看图怎么一步步走）
for update in app.stream({"messages": [("user", "你好")]}):
    print(update)     # 每个节点执行完输出一次增量
```

`app.stream` 是排障神器：每个节点的输出按顺序打印，相当于第 6 周手写日志的框架版。另外强烈建议用 LangSmith（框架官方 tracing）看一次完整 trace，可视化每步输入输出。

## 5. 本周项目实战：重构手写 Agent

任务：把第 6 周 `agent.py` 重构成 LangGraph 版 `week07/graph_agent.py`：

1. State 用 `Annotated[list, add_messages]` 承载 messages
2. `call_model` 节点：调你第 6 周的 `call_llm`
3. `execute_tools` 节点：循环执行所有 `tool_calls` 并返回 tool 消息列表（保留异常回填护栏！）
4. 条件边 `route` 判断 `tool_calls`
5. 保留 `calculator` / `get_weather` / `read_note` 三个工具

参考骨架：

```python
"""week07/graph_agent.py —— 第6周 Agent 的 LangGraph 重构"""
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# ... 复用第6周的 call_llm / execute_tool / build_tools / SYSTEM ...

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

def call_model(state: AgentState) -> dict:
    msg = call_llm_sync(list(state["messages"]), build_tools())   # 第6周的函数
    return {"messages": [msg]}

def execute_tools(state: AgentState) -> dict:
    last = state["messages"][-1]
    results = []
    for tc in last.tool_calls:
        result = run_tool_safe(tc["function"]["name"], tc["function"]["arguments"])
        results.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    return {"messages": results}

def route(state: AgentState) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else END

builder = StateGraph(AgentState)
builder.add_node("model", call_model)
builder.add_node("tools", execute_tools)
builder.add_edge(START, "model")
builder.add_conditional_edges("model", route)
builder.add_edge("tools", "model")
app = builder.compile()

if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) or "查一下苏州现在多少度，比25度高几度？"
    print(app.invoke({"messages": [("user", task)]})["messages"][-1].content)
```

验收动作：跑通第 6 周全部 5 个测试任务，结果应一致。

## 6. 框架替你做了什么（验收必答题）

逐条对照，向自己证明「没有魔法」：

| 第 6 周手写的 | LangGraph 对应物 |
| --- | --- |
| `history` list + 手动 append | State + `add_messages` reducer |
| for/while 主循环 | 图的固定边 tools→model + 引擎内置循环 |
| `if tool_calls` 判断 | 条件边 `route` |
| MAX_TURNS | `recursion_limit` |
| 每轮 print 日志 | `app.stream` / LangSmith trace |
| （手写版没有的）并行分支、子图、持久化 | 框架原生能力，第 8 周起解锁 |

## 7. 验收自测

- [ ] 重构后 5 个测试任务全部与手写版行为一致
- [ ] 在纸上画出自己 Agent 的图结构（节点、固定边、条件边、END）
- [ ] 能流利回答上表的「框架替你做了什么」
- [ ] 能解释 `Annotated[list, add_messages]` 中每个部分的作用
- [ ] 代码提交 git

自测题：
1. 节点返回 `{"messages": [msg]}` 时，state 里是只剩这一条还是追加？为什么？
2. 条件边函数的返回值是什么？它和 Navigation 的 route 有什么相似之处？
3. `recursion_limit` 对应你手写版的哪个护栏？触发后会发生什么？

## 8. 衔接第 8 周

现在你的 Agent 是个「一锤子买卖」：图跑完状态就没了。第 8 周给图装上 Checkpointer——进程重启对话可恢复，再学会 interrupt：在「删除文件」这类危险操作前中断等人确认。对照安卓：onSaveInstanceState + 前台弹窗确认的组合拳。第 8 周见。
