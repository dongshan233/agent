# 第 5 周：Function Calling + ReAct + 上下文管理

> 阶段二 · 第 5 周。**全程最核心的一周，宁可慢不可跳。** 计划里预留了缓冲：如果一周吃不下，可以拆成两周。

## 学习目标

1. 彻底搞懂 Function Calling 的执行真相（模型不执行任何东西）
2. 会设计合格的工具 schema
3. 理解 ReAct 循环和四大失败模式
4. 理解上下文管理三原则
5. 产出：带计算器 + 天气工具的聊天机器人

## 1. Function Calling 的真相（先破除误解）

**误解**：模型「会调用函数」。
**真相**：模型只做一件事——**按你给的 JSON Schema，生成一段「我想调用什么工具、参数是什么」的 JSON 文本**。

```
你 ──[messages + 工具schema列表]──→ 模型
模型 ──[返回: "我要调 get_weather(city='苏州')"]──→ 你
你   ──[你的代码真正执行函数，拿到结果]──→ 
你   ──[把结果作为 tool 消息塞回 messages]──→ 模型
模型 ──[基于结果生成自然语言回答]──→ 你
```

模型是**大脑**，你的代码才是**手**。这个循环的编排者，是客户端（你的代码）——第 6 周你手写它，第 7 周框架替你写它。

### 1.1 一次工具调用的完整消息流转（验收必背）

四个角色，四条消息：

```python
messages = [
    {"role": "system",    "content": "..."},
    {"role": "user",      "content": "苏州今天多少度？"},
    # ↓ 模型返回的第一条 assistant 消息：不带 content，带 tool_calls
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_abc", "type": "function",
         "function": {"name": "get_weather", "arguments": "{\"city\": \"苏州\"}"}}
    ]},
    # ↓ 你执行函数后回填的 tool 消息：must 用上一步的 id 对应
    {"role": "tool", "tool_call_id": "call_abc",
     "content": "{\"temp_c\": 18, \"condition\": \"多云\"}"},
    # 再发给模型 → 返回带 content 的 assistant 回答
]
```

注意三个细节：
- `arguments` 是**字符串形式的 JSON**，要自己 `json.loads`
- 回填的 `tool` 消息必须带 `tool_call_id`，与 `tool_calls[].id` 对应，否则 API 报错
- 模型第二次看到这份 messages 时，靠 `tool_calls` + `tool` 这对组合知道「我之前请求了什么、结果是什么」

## 2. 工具 schema 设计（工程问题，不是玄学）

请求里新增 `tools` 字段，OpenAI 兼容格式：

```python
from pydantic import BaseModel, Field

class GetWeatherArgs(BaseModel):
    """查询指定城市当前天气。"""   # docstring 会成为 schema description！
    city: str = Field(description="城市名，中文如'苏州'，拼音如'suzhou'")
    unit: str = Field(default="celsius", description="温度单位: celsius | fahrenheit")

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取指定城市的当前天气（温度、天气状况）。当用户询问天气时使用。",
        "parameters": GetWeatherArgs.model_json_schema(),   # 第2周的 pydantic 直接产出 schema
    },
}]
```

### 2.1 schema 四原则

| 原则 | 反例 | 正例 |
| --- | --- | --- |
| 描述具体，说清「什么时候用、什么时候不用」 | `"获取天气"` | `"获取指定城市**当前**天气。不要用于历史天气或预报。"` |
| 参数类型/枚举写全 | `unit: str` 无约束 | `Literal["celsius", "fahrenheit"]` |
| 给可选项列表 | description 里含糊其辞 | 明确枚举值及示例 |
| 参数名自解释 | `q: str` | `city: str` |

**描述含糊 = 模型传错参数**。这不是玄学，是检索匹配：模型的工具选择本质上读你的 description 做语义匹配。描述里写上「不要用于 X」能有效防止误触发。

### 2.2 请求与响应中的关键开关

请求 payload 新增：`"tools": [...], "tool_choice": "auto"`（`auto`=模型自己决定；`"none"`=禁用；指定名字=强制调用）。

响应的 `finish_reason` 可能是 `"tool_calls"`，`choices[0].message.tool_calls` 是数组——**可能一次返回多个工具调用**（并行调用），每个都要执行并各自回填一条 `tool` 消息。

## 3. ReAct 循环

ReAct = Reason + Act，Agent 的基本执行模型：

```
Thought（模型内部推理）→ Action（发起 tool_calls）→ Observation（tool 消息回填的结果）
→ Thought（评估结果）→ ... → Final Answer（finish_reason=stop 的纯文本回复）
```

第 4 周的聊天机器人是「一问一答」；加了工具后变成「多步循环」——你的代码要在工具消息回填后**再次调用模型**，直到它给出不含 `tool_calls` 的最终回答。这个「调模型→判断→执行→回填→再调模型」的 while 循环，就是 Agent 本体，第 6 周正式手写它。

## 4. 四大失败模式（工程排障手册）

| 模式 | 现象 | 对策 |
| --- | --- | --- |
| **死循环** | 反复调同一工具、参数不变，永不停止 | 设最大迭代轮次（10 轮左右）强制退出；日志里检测「连续 N 次相同调用」 |
| **上下文爆炸** | 轮次太多塞满窗口，报错或成本失控 | 主动剪枝：保留 system + 最近 N 轮 + 全部工具调用对 |
| **早停** | 没拿到关键信息就宣布完成（如没查天气就直接编造答案） | system prompt 里明确「必须先获取事实再回答」；对关键结论要求引用工具结果 |
| **过度思考** | 推理模型反复犹豫、绕圈子不执行 | 给推理预算上限；简化工具数量（>10 个工具时选择错误率明显上升） |

本周先**认识**它们，第 6 周在代码里逐个加护栏，第 12 周在评估中量化它们。

## 5. 上下文管理三原则

1. **长窗口 ≠ 好用（context rot）**：窗口塞得下不等于读得好——无关内容越多，关键信息的利用率越低。宁可精简，不要囤积。
2. **Lost in the middle**：模型对上下文的注意力呈 U 型——**开头和结尾记得牢，中间容易忽略**。所以：system 放开头，最新消息/关键约束放结尾，历史性细节塞中间。
3. **主动剪枝**：不要无限追加历史。常见策略：
   - 保留 system + 最近 K 轮对话
   - 旧的 assistant 长回答压缩成一句话摘要
   - 工具的原始返回（可能很大，如整个 JSON）用完后替换成摘要

对照安卓：≈ 内存管理——窗口是硬预算，被动 OOM 不如主动 LRU。

## 6. 本周项目实战：给聊天机器人装手

需求：第 4 周机器人 + 2 个工具：
1. `calculator`：精确四则运算（模型心算不可靠，这是工具的经典用法）
2. `get_weather`：接一个真实免费天气 API（如 open-meteo.com，无需 Key）

`week05/toolbot.py` 核心骨架：

```python
"""带工具的聊天机器人。运行: uv run python toolbot.py"""
import json
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
BASE, KEY, MODEL = (os.environ[k] for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))


# ---------- 工具实现 ----------
def calculator(expression: str) -> str:
    """安全求值：只允许数字和四则运算符。"""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "错误：表达式包含非法字符"
    try:
        return str(eval(expression))   # 练习用；生产环境应换成 AST 白名单求值
    except Exception as e:
        return f"计算失败: {e}"


async def get_weather(city: str) -> str:
    geo = await httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": city, "language": "zh"}, timeout=10)
    geo.raise_for_status()
    hits = geo.json().get("results")
    if not hits:
        return f"错误：找不到城市 {city}"
    loc = hits[0]
    wx = await httpx.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": loc["latitude"], "longitude": loc["longitude"],
                                 "current_weather": True}, timeout=10)
    wx.raise_for_status()
    cur = wx.json()["current_weather"]
    return json.dumps({"city": loc["name"], "temp_c": cur["temperature"],
                       "wind_kmh": cur["windspeed"]}, ensure_ascii=False)


# ---------- 工具 schema（pydantic 生成）----------
class CalcArgs(BaseModel):
    """执行精确的数学四则运算。需要数学计算（加减乘除）时使用，不要心算。"""
    expression: str = Field(description="数学表达式，如 '18 + 7' 或 '(3+4)*2'")

class WeatherArgs(BaseModel):
    """查询指定城市当前气温和风速。用户询问天气时使用。"""
    city: str = Field(description="中文城市名，如'苏州'")

TOOL_FUNCS = {"calculator": calculator, "get_weather": get_weather}


def build_tools() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": "calculator",
            "description": CalcArgs.__doc__,
            "parameters": CalcArgs.model_json_schema()},
        },
        {"type": "function", "function": {
            "name": "get_weather",
            "description": WeatherArgs.__doc__,
            "parameters": WeatherArgs.model_json_schema()},
        },
    ]


# ---------- 主循环 ----------
async def run_turn(history: list[dict], tools: list[dict]) -> None:
    url, headers = f"{BASE}/chat/completions", {"Authorization": f"Bearer {KEY}"}
    payload = {"model": MODEL, "messages": history, "tools": tools, "tool_choice": "auto"}
    resp = await httpx.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]

    if not msg.get("tool_calls"):                  # 最终回答
        print(f"\n助手> {msg['content']}")
        history.append({"role": "assistant", "content": msg["content"]})
        return

    history.append({"role": "assistant", "content": msg.get("content"),
                    "tool_calls": msg["tool_calls"]})
    for tc in msg["tool_calls"]:                   # 逐个执行并回填
        name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        print(f"  [调用工具] {name}({args})")
        result = TOOL_FUNCS[name](**args)
        if name == "get_weather":
            result = await result                  # get_weather 是协程
        print(f"  [工具结果] {result}")
        history.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

    await run_turn(history, tools)                 # 带着结果再问模型（简化版递归循环）


async def main() -> None:
    tools = build_tools()
    history = [{"role": "system", "content": "你是能使用工具的助手。数学必须用 calculator 工具。"}]
    while True:
        user = input("\n你> ").strip()
        if user in ("/exit", ""):
            break
        history.append({"role": "user", "content": user})
        await run_turn(history, tools)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**必须完成的实验**（对应验收第 3 条）：
1. 提问「苏州今天多少度，比 25 度高几度」→ 应触发 `get_weather` + `calculator` 两次调用
2. 把 `WeatherArgs.city` 的 description 改成只写 `"城市"` → 重跑，观察模型是否传错参数（如传英文名、传「今天的天气」整句话）
3. 记录实验前后模型行为差异到 `week05/NOTES.md`

## 7. 验收自测

- [ ] 「苏州温度 vs 25 度」测试通过，两次工具调用链路正确
- [ ] 能口头讲清一次工具调用的 4 条消息流转（user / assistant+tool_calls / tool / assistant）
- [ ] 模糊描述实验已做并记录现象
- [ ] 代码提交 git

自测题：
1. 模型返回的 `arguments` 是什么类型？你要做哪两步才能拿到真正的参数值？
2. 为什么回填 tool 消息时必须带 `tool_call_id`？
3. `finish_reason=tool_calls` 和 `finish_reason=stop` 分别意味着什么？
4. 一个工具的返回结果很大（比如 10KB JSON），轮次多了会发生什么？你怎么处理？

## 8. 衔接第 6 周

你已经在 `run_turn` 里零星写了 Agent 循环的原型。第 6 周把它正式化：独立的 `while` 主循环、最大轮次护栏、异常兜底、全链路日志，再加第 3 个工具，凑成约 150 行的完整手写 Agent。第 6 周见。
