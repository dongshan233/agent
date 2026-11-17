# 第 6 周：手写最小 Agent（无框架）

> 阶段三 · 第 6 周。目标：不用任何框架，约 150 行实现完整 Agent 循环。**这一步搞透，后面学框架时你知道每个 API 在替你做什么。**

## 学习目标

1. 把第 5 周的片段代码组织成正式的 Agent 主循环
2. 加上三大护栏：最大轮次、异常兜底、全链路日志
3. 验证模型能自主规划多工具组合
4. 用 5 个测试任务（含 1 个无解）做首轮评估，写出复盘

## 1. Agent 的定义（一句话）

> Agent = **LLM + 工具 + 循环**。模型在循环中反复「看当前状态 → 决定下一步动作」，直到任务完成或预算耗尽。

三个成分缺一不可：没有工具只是聊天机器人；没有循环只是单次工具调用；没有护栏就是定时炸弹。

## 2. 主循环设计（先画图再写码）

```
                 ┌─────────────────────────────────┐
                 │  while 轮次 < MAX_TURNS:          │
                 │    1. 调模型（带全部 messages+tools）│
                 │    2. finish_reason == stop?      │──是──→ 返回最终答案
                 │    3. 否则执行所有 tool_calls       │
                 │    4. 结果回填 tool 消息            │
                 │    5. 轮次 +1                     │
                 └────────────  再进下一轮 ←─────────┘
                                  │
                          轮次耗尽 → 优雅退出
```

对照第 5 周的递归版 `run_turn`：改成显式 `while` 有两个好处——能数轮次（护栏）、能打日志（可观测）。**显式循环是工程正确做法**。

## 3. 三大护栏

| 护栏 | 防什么 | 实现 |
| --- | --- | --- |
| 最大轮次 | 死循环（失败模式 #1） | `while turn < 10`；耗尽时把状态如实告诉模型让它总结，或直接返回失败说明 |
| 工具异常兜底 | 一个工具崩导致整个 Agent 崩 | 工具执行包 `try/except`，**把异常文本作为工具结果回填**（模型能读到并改变策略） |
| 全链路日志 | 排障时黑箱 | 每轮打印：轮次号、模型想调什么工具、什么参数、结果摘要 |

其中「异常回填」是最反直觉也最重要的一条：**不要把异常吞掉或让进程崩溃，要让模型看见错误**。模型看到 `"错误：城市名无效"` 会自己换个参数重试——这就是所谓的自愈能力。

## 4. 参考实现（约 150 行完整版）

`week06/agent.py`：

```python
"""手写最小 ReAct Agent（无框架）。运行: uv run python agent.py "任务描述"""
import asyncio
import json
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
BASE, KEY, MODEL = (os.environ[k] for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))
MAX_TURNS = 10


# ---------- 工具层 ----------
def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "错误：表达式包含非法字符"
    try:
        return str(eval(expression))
    except Exception as e:
        return f"计算失败: {e}"


async def get_weather(city: str) -> str:
    geo = await httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": city, "language": "zh"}, timeout=10)
    hits = geo.json().get("results")
    if not hits:
        return f"错误：找不到城市 {city}"
    loc = hits[0]
    wx = await httpx.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": loc["latitude"], "longitude": loc["longitude"],
                                 "current_weather": True}, timeout=10)
    cur = wx.json()["current_weather"]
    return json.dumps({"city": loc["name"], "temp_c": cur["temperature"]}, ensure_ascii=False)


def read_note(title: str) -> str:
    """读取本地 notes/ 目录下的笔记文件。"""
    path = f"notes/{title}.md"
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"错误：笔记 {path} 不存在"


class CalcArgs(BaseModel):
    """执行精确数学四则运算。任何需要计算的场景必须用它，禁止心算。"""
    expression: str = Field(description="数学表达式，如 '18 + 7'")

class WeatherArgs(BaseModel):
    """查询指定城市当前气温。"""
    city: str = Field(description="中文城市名，如'苏州'")

class NoteArgs(BaseModel):
    """读取指定标题的本地笔记内容。"""
    title: str = Field(description="笔记标题（不含扩展名）")

TOOL_FUNCS = {"calculator": calculator, "get_weather": get_weather, "read_note": read_note}


def build_tools() -> list[dict]:
    out = []
    for args_cls in (CalcArgs, WeatherArgs, NoteArgs):
        name = {CalcArgs: "calculator", WeatherArgs: "get_weather", NoteArgs: "read_note"}[args_cls]
        out.append({"type": "function", "function": {
            "name": name, "description": args_cls.__doc__,
            "parameters": args_cls.model_json_schema()}})
    return out


# ---------- Agent 核心 ----------
SYSTEM = """你是一个任务执行 Agent。可用工具见 tools 定义。
规则：
1. 需要事实数据（天气、笔记内容）时必须先调用工具获取，禁止编造。
2. 数学计算必须用 calculator，禁止心算。
3. 拿到足够信息后立即给出最终答案，不要多余的工具调用。"""


async def call_llm(history: list[dict], tools: list[dict]) -> dict:
    resp = await httpx.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {KEY}"},
        json={"model": MODEL, "messages": history, "tools": tools, "tool_choice": "auto"},
        timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]


async def execute_tool(name: str, args: dict) -> str:
    try:
        fn = TOOL_FUNCS.get(name)
        if fn is None:
            return f"错误：未知工具 {name}"
        result = fn(**args)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result)
    except Exception as e:                      # 护栏2：异常回填而非崩溃
        return f"工具执行异常: {type(e).__name__}: {e}"


async def run_agent(task: str, max_turns: int = MAX_TURNS) -> str:
    tools = build_tools()
    history: list[dict] = [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": task}]
    for turn in range(1, max_turns + 1):
        msg = await call_llm(history, tools)
        tool_calls = msg.get("tool_calls")

        if not tool_calls:                      # 最终回答
            print(f"[第{turn}轮] 最终回答")
            return msg.get("content") or ""

        print(f"[第{turn}轮] 请求工具: " +
              ", ".join(f"{tc['function']['name']}({tc['function']['arguments']})"
                        for tc in tool_calls))
        history.append({"role": "assistant", "content": msg.get("content"),
                        "tool_calls": tool_calls})
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            result = await execute_tool(tc["function"]["name"], args)
            print(f"          结果: {result[:120]}")
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    return f"（达到最大轮次 {MAX_TURNS}，未能完成任务。已产生的部分信息见上方日志。）"


if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) or "查一下苏州现在多少度，比25度高几度？"
    print(asyncio.run(run_agent(task)))
```

**逐行读懂后合上文件自己默写主循环**（`run_agent` 的 for 循环那 20 行）——这是本周最重要的练习，第 7 周起框架会把它藏起来，你必须先亲手拥有它。

## 5. 验证多工具自主规划

加第 3 个工具（`read_note`，读取本地 markdown 笔记）后，测试组合任务：

> 「读一下 notes/日程.md 里说周五要不要带伞，如果明天苏州有雨帮我确认」

预期模型自主编排：`read_note` → `get_weather` → 综合判断回答。**你不写任何编排逻辑**——规划发生在模型内部，你的循环只负责执行。观察日志确认调用顺序不是你预设的。

## 6. 测试与复盘（周末任务）

准备 5 个测试任务（至少 1 个故意无解）：

| # | 任务 | 类型 | 预期 |
| --- | --- | --- | --- |
| 1 | 苏州温度比 25 高几度 | 两步链 | 成功 |
| 2 | 读笔记并回答其中问题 | 检索 | 成功 |
| 3 | 天气+计算组合 | 多工具 | 成功 |
| 4 | 「读 notes/不存在的文件里的密码」 | **无解** | 优雅报告失败，不死循环 |
| 5 | 你自选 | 边界 | 记录 |

每个任务记录：完成/失败、轮次数、失败原因（对照四大失败模式归类）。写 200 字复盘进 `week06/RETRO.md`，重点回答：**哪里最容易坏？**（常见答案：工具描述不够准、无解任务反复重试、结果太长挤占上下文——保留你的观察，第 12 周评估要用）

## 7. 验收自测

- [ ] 「查 A → 用 A 计算 → 汇总回答」两步以上任务通过
- [ ] 无解任务不死循环，达到轮次上限后优雅退出（试一下把 MAX_TURNS 改成 2 复现）
- [ ] 日志能完整还原每一步决策（拿日志给人看，对方能复述 Agent 干了什么）
- [ ] 合上文件能默写主循环
- [ ] `week06/RETRO.md` 复盘完成，代码提交 git

自测题：
1. 为什么工具异常要作为字符串回填，而不是抛出终止进程？
2. 「agent 的规划能力」到底在哪里？在你的循环代码里吗？
3. 如果工具结果是一个 20KB 的 JSON，你的 Agent 会出现什么问题？

## 8. 衔接第 7 周

你已经拥有一个约 150 行的可用 Agent。但它有痛点：状态就是那个 `history` 列表、控制流藏在 for 循环里、没法持久化、没法在中间插入人工决策。第 7 周开始，LangGraph 把「状态、节点、边」变成一等公民——你会发现图里的每个概念都对应你手写过的一段代码。第 7 周见。
