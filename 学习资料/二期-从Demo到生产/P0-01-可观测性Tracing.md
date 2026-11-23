# P0-01 可观测性 Tracing：给 Agent 装上黑匣子

> P0 生产化深挖 · 模块 1 / 4。**前置**：二期 `README.md` §4 的「0 号补丁」已完成、`server/base.py` 可运行并已 commit。
> 本模块不改动一期核心循环，只加一个新文件 + 接一个 hooks + 在 SSE 里加一个字段。

## 学习目标

1. 理解 trace / span 的树形结构，能画出一次 Agent 运行的执行树
2. 手工插桩，给「整次运行 / 每次模型调用 / 每次工具调用」各打 span
3. 不依赖任何云服务，落盘 JSONL 并能一键打印调用树
4. 用 trace 复现一期第 5 周的「死循环」失败模式，体验排障差异
5. 知道生产环境如何一行切换到 OpenTelemetry / Langfuse

---

## 1. 为什么第一个做（对照安卓）

一期第 6 周你给手写 Agent 加了「全链路日志」：每轮 `print("[第N轮] 请求工具: ...")`。它够你学循环，但一到真实排障就不够用了：

| 平铺日志的问题 | 后果 |
| --- | --- |
| 没有父子关系 | 看不出「这个 tool 结果是哪次 model 决策触发的」 |
| 没有耗时与 token | 无法回答「慢在哪一步、钱烧在哪一步」 |
| 跨 async / 跨请求串不起来 | FastAPI 并发两个会话时日志混在一起 |
| 进程重启就没了 | 线上问题无法复现 |

对照安卓，这非常好懂：

| 安卓 | Agent 可观测性 |
| --- | --- |
| Logcat 单行 `Log.d` | 一期 `print` |
| `Trace.beginSection()` / systrace | **span**（一段有起止的执行） |
| Android Studio Profiler 的调用栈 + Network 面板 | **trace 树**（父子 span + 属性 + 耗时） |
| OkHttp `Interceptor` | 本模块的 **hooks**（业务代码不动，挂观察者） |

**为什么排 P0 第一**：P0-02 的评估需要轮次、工具调用序列、延迟、token、错误类型——这些全在 trace 里。没有 trace，评估只能人工数日志；有了 trace，评估是「读结构化数据」。这是后面三个模块的地基。

> 2026 年生产实践的一致结论：可观测性要 **day one 就接入**，上线后才补的团队，第一个月基本是瞎的。

---

## 2. 概念：一次运行是一棵树

一次用户请求 = 一个 **trace**（一个 `trace_id`）。里面每一步 = 一个 **span**，span 有父 span，形成树。span 上挂 **attributes**（元数据）。

```
trace a1b2c3  agent.run                          duration 2310ms  tokens 812  cost ¥0.0098
├── llm.qwen-plus          turn=1  410ms  tool_calls=1  prompt=210 comp=38
│   └── tool.get_weather   turn=1  180ms  args={"city":"苏州"}  result_len=96
├── llm.qwen-plus          turn=2  520ms  tool_calls=1  prompt=340 comp=26
│   └── tool.calculator    turn=2    2ms  args={"expression":"18-25"}  result_len=3
└── llm.qwen-plus          turn=3 1180ms  tool_calls=0  prompt=380 comp=64
```

| 字段 | 含义 | 一期对应物 |
| --- | --- | --- |
| `trace_id` | 一次请求的唯一 id | 第 8 周的 `thread_id`（但trace 是单次运行，thread 是会话） |
| `span.name` | 步骤名 | `[第N轮]` 日志 |
| `parent_id` | 父 span | 日志里没有 |
| `duration_ms` | 这一步耗时 | 日志里没有 |
| `attributes` | tokens / cost / args / error | 日志里只有结果前 120 字符 |
| `status` | ok / error | 日志里没有 |

**注意 `trace_id` 与 `thread_id` 的区别**：一个会话（thread）可以有多轮请求，每轮请求是一个独立 trace。对照安卓：`thread_id` ≈ 用户会话，`trace_id` ≈ 一次点击引发的那条完整调用链。

---

## 3. 逐步操作

### 步骤 1：装依赖

```powershell
uv add opentelemetry-api opentelemetry-sdk   # 生产导出器用，本模块教学实现不强依赖
```

本模块**主实现用纯标准库手写**（零配置、一定跑得通、便于理解结构），步骤 6 再给换成 OTel / Langfuse 的替换片段。教学先弄懂「trace 到底记了什么」，再谈接哪个平台。

顺手建目录和包标记：

```powershell
mkdir -p eval/traces scripts
New-Item -ItemType File eval/__init__.py
New-Item -ItemType File server/__init__.py
```

（`eval/__init__.py` 是为了后面能用 `uv run python -m eval.view_trace`。）

### 步骤 2：新建 `server/observability.py`

```python
"""server/observability.py —— 零依赖 trace 实现（教学版）。

设计要点：
1. 每个请求一个 Trace 实例（绝不做全局单例，否则并发时 span 父子会串）。
2. span 用两种方式产生：
   - async with trace.span(...)  包住一段代码，自动计时、自动记异常
   - trace.record(...)           事后补记（hooks 回调式插桩用这个）
3. 落盘 JSONL：一行一个 trace，不依赖任何外部服务。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from server.base import AgentResult, ModelResponse, estimate_cost

TRACE_DIR = Path(os.getenv("TRACE_DIR", "eval/traces"))


@dataclass
class Span:
    span_id: str
    parent_id: str | None
    name: str
    start_ms: float
    end_ms: float | None = None
    duration_ms: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def finish(self, error: BaseException | str | None = None) -> "Span":
        self.end_ms = time.time() * 1000
        self.duration_ms = round(self.end_ms - self.start_ms, 2)
        if error:
            self.status = "error"
            self.error = str(error)
        return self


class Trace:
    def __init__(self, name: str, trace_id: str | None = None, **attrs: Any):
        self.trace_id = trace_id or uuid.uuid4().hex
        self.name = name
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.spans: list[Span] = []
        self.stack: list[Span] = []
        self.root = self._new_span(name, None, **attrs)
        self.spans.append(self.root)
        self.stack.append(self.root)      # 根 span 常驻栈底

    def _new_span(self, name: str, parent: Span | None, **attrs: Any) -> Span:
        return Span(
            span_id=uuid.uuid4().hex[:12],
            parent_id=parent.span_id if parent else None,
            name=name,
            start_ms=time.time() * 1000,
            attributes=dict(attrs),
        )

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any):
        """包住一段异步代码，自动计时 + 自动记异常。生产插桩推荐这个。"""
        parent = self.stack[-1] if self.stack else None
        sp = self._new_span(name, parent, **attrs)
        self.spans.append(sp)
        self.stack.append(sp)
        try:
            yield sp
        except Exception as e:
            sp.finish(error=e)
            raise
        else:
            sp.finish()
        finally:
            self.stack.pop()

    def record(self, name: str, duration_ms: float, **attrs: Any) -> Span:
        """事后补记一个已完成的 span（hooks 回调里用）。起点按耗时反推。"""
        parent = self.stack[-1] if self.stack else None
        error = attrs.pop("error", None)
        status = attrs.pop("status", "ok")
        sp = self._new_span(name, parent, **attrs)
        sp.start_ms -= duration_ms          # 近似起点，耗时以实测为准
        sp.duration_ms = round(duration_ms, 2)
        sp.end_ms = sp.start_ms + duration_ms
        sp.status = "error" if error else status
        sp.error = str(error) if error else None
        self.spans.append(sp)
        return sp

    def finish(self, error: str | None = None) -> "Trace":
        self.root.finish(error=error)
        self.stack.clear()
        return self

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "started_at": self.started_at,
            "spans": [asdict(s) for s in self.spans],
        }

    def save(self) -> Path:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        path = TRACE_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
        return path


class TracingHooks:
    """实现 README §4.3 的 hooks 接口。传给 run_task(hooks=...) 即可。"""

    def __init__(self, task: str, thread_id: str, trace_id: str | None = None):
        self.trace = Trace(
            "agent.run",
            trace_id=trace_id,
            task=task[:200],
            thread_id=thread_id,
            kind="root",
        )

    async def on_model(self, r: ModelResponse, turn: int) -> None:
        self.trace.record(
            f"llm.{r.model}", r.latency_ms,
            kind="model", turn=turn,
            prompt_tokens=r.usage.get("prompt_tokens", 0),
            completion_tokens=r.usage.get("completion_tokens", 0),
            total_tokens=r.usage.get("total_tokens", 0),
            cost_yuan=estimate_cost(r.usage),
            tool_calls=len(r.tool_calls),
            content=r.content[:200],
        )

    async def on_tool(self, name: str, args: dict, out: str,
                      turn: int, elapsed_ms: float) -> None:
        self.trace.record(
            f"tool.{name}", elapsed_ms,
            kind="tool", turn=turn,
            args=json.dumps(args, ensure_ascii=False)[:300],
            result=out[:500],              # 截断：呼应 P0-03 的工具返回瘦身
            result_len=len(out),
            status="error" if out.startswith(("错误", "工具执行异常")) else "ok",
        )

    async def on_end(self, result: AgentResult) -> None:
        turns = max((t["turn"] for t in result.tool_calls), default=0)
        self.trace.root.attributes.update({
            "answer": result.answer[:200],
            "turns": turns,
            "tool_call_count": len(result.tool_calls),
            "total_tokens": result.usage.get("total_tokens", 0),
            "cost_yuan": estimate_cost(result.usage),
            "latency_ms": result.latency_ms,
        })
        self.trace.finish(error=result.error)
        path = self.trace.save()
        print(f"[trace] {self.trace.trace_id} -> {path}")
```

**三个容易看漏的地方**：

1. `Trace` 每个请求 new 一个，`stack` 是实例变量。**不要改成全局单例**——FastAPI 并发时两个请求的 span 会互相认错父亲。
2. `on_tool` 里对结果截断到 500 字符。不是偷懒：一期第 5 周讲过「工具返回 20KB JSON 会挤爆上下文」，trace 同理，落盘也要有预算。
3. `status="error"` 的判定靠字符串前缀，这是沿用一期「异常回填为字符串」的约定（第 6 周护栏 2）。

### 步骤 3：建两个自包含的演示工具（不依赖网络）

`scripts/demo_tools.py`——让本模块**不接真实天气 API 也能跑通**，先验证插桩，再回主线接一期的 `week06` 工具。

```python
"""scripts/demo_tools.py —— 仅用于 P0-01/02 自测的本地工具。"""
import json

from pydantic import BaseModel, Field


class CalcArgs(BaseModel):
    """执行精确数学四则运算。任何需要计算的场景必须用它，禁止心算。"""
    expression: str = Field(description="数学表达式，如 '18 - 25'")


class WeatherArgs(BaseModel):
    """查询指定城市当前气温。用户询问天气时使用。"""
    city: str = Field(description="中文城市名，如'苏州'")


def calculator(expression: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return "错误：表达式包含非法字符"
    try:
        return str(eval(expression))       # 教学用；P0-04 会换成 AST 白名单
    except Exception as e:
        return f"计算失败: {e}"


def fake_weather(city: str) -> str:
    return json.dumps({"city": city, "temp_c": 18, "condition": "多云"},
                      ensure_ascii=False)


TOOL_FUNCS = {"calculator": calculator, "get_weather": fake_weather}


def build_tools() -> list[dict]:
    return [
        {"type": "function", "function": {
            "name": "calculator", "description": CalcArgs.__doc__,
            "parameters": CalcArgs.model_json_schema()}},
        {"type": "function", "function": {
            "name": "get_weather", "description": WeatherArgs.__doc__,
            "parameters": WeatherArgs.model_json_schema()}},
    ]
```

### 步骤 4：跑一次，看 trace

`scripts/try_trace.py`：

```python
"""scripts/try_trace.py —— 运行: uv run python scripts/try_trace.py"""
import asyncio
import sys

from scripts.demo_tools import TOOL_FUNCS, build_tools
from server.base import run_task
from server.observability import TracingHooks


async def main() -> None:
    task = " ".join(sys.argv[1:]) or "查一下苏州现在多少度，比25度高几度？"
    hooks = TracingHooks(task, thread_id="demo-1")
    r = await run_task(
        task,
        thread_id="demo-1",
        tools=build_tools(),
        tool_funcs=TOOL_FUNCS,
        hooks=hooks,
    )
    print(f"\n回答> {r.answer}")
    print(f"轮次={max((t['turn'] for t in r.tool_calls), default=0)} "
          f"工具调用={len(r.tool_calls)} "
          f"token={r.usage.get('total_tokens')} "
          f"耗时={r.latency_ms}ms "
          f"error={r.error}")


if __name__ == "__main__":
    asyncio.run(main())
```

```powershell
uv run python scripts/try_trace.py
```

预期输出（数字会变，结构不变）：

```
[trace] 9f3c... -> eval/traces/2026-11-23.jsonl

回答> 苏州现在 18 度，比 25 度低 7 度。
轮次=2 工具调用=2 token=812 耗时=2310.44ms error=None
```

**这一步没跑通就不要往下走**，按 §4 踩坑表处理。

### 步骤 5：一键打印 trace 树

`eval/view_trace.py`：

```python
"""eval/view_trace.py —— 打印一棵 trace 树。
运行: uv run python -m eval.view_trace [trace_id前8位]
不传参数则打印当天最后一条。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

TRACE_DIR = Path("eval/traces")


def load_last(prefix: str | None = None) -> dict:
    files = sorted(TRACE_DIR.glob("*.jsonl"))
    if not files:
        raise SystemExit(f"没有 trace 文件，先跑 scripts/try_trace.py（目录 {TRACE_DIR}）")
    lines = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(json.loads(line))
    if prefix:
        lines = [t for t in lines if t["trace_id"].startswith(prefix)]
    if not lines:
        raise SystemExit(f"找不到 trace_id 以 {prefix} 开头的记录")
    return lines[-1]


def main() -> None:
    t = load_last(sys.argv[1] if len(sys.argv) > 1 else None)
    spans = t["spans"]
    by_id = {s["span_id"]: s for s in spans}
    children: dict[str | None, list[dict]] = {}
    for s in spans:
        children.setdefault(s["parent_id"], []).append(s)

    root = spans[0]
    print(f"trace {t['trace_id']}  {t['started_at']}")

    def walk(s: dict, depth: int = 0) -> None:
        a = s["attributes"]
        bits = [f"{s['duration_ms']}ms"]
        if a.get("kind") == "model":
            bits.append(f"{a.get('total_tokens')}tok "
                        f"¥{a.get('cost_yuan')} "
                        f"tool_calls={a.get('tool_calls')}")
        if a.get("kind") == "tool":
            bits.append(f"args={a.get('args')} len={a.get('result_len')}")
        if a.get("kind") == "root":
            bits.append(f"turns={a.get('turns')} "
                        f"tools={a.get('tool_call_count')} "
                        f"tok={a.get('total_tokens')} "
                        f"¥{a.get('cost_yuan')}")
        flag = "  ERROR" if s["status"] == "error" else ""
        print("  " * depth + f"└─ {s['name']}  [{' | '.join(bits)}]{flag}")
        if s["error"]:
            print("  " * (depth + 1) + f"└─ {s['error']}")
        for c in children.get(s["span_id"], []):
            walk(c, depth + 1)

    walk(root)
    for orphan in children.get(None, [])[1:]:
        walk(orphan)


if __name__ == "__main__":
    main()
```

```powershell
uv run python -m eval.view_trace
```

预期（这就是 §2 那张图的真实输出）：

```
trace 9f3c...  2026-11-23T12:10:03
└─ agent.run  [2310.44ms | turns=2 | tools=2 | tok=812 | ¥0.0098]
  └─ llm.qwen-plus  [410.2ms | 248tok ¥0.0021 tool_calls=1]
  └─ tool.get_weather  [0.31ms | args={"city": "苏州"} len=52]
  └─ llm.qwen-plus  [520.7ms | 366tok ¥0.0042 tool_calls=1]
  └─ tool.calculator  [0.12ms | args={"expression": "18-25"} len=3]
  └─ llm.qwen-plus  [1180.5ms | 444tok ¥0.0053 tool_calls=0]
```

> 注意：hooks 是「调用返回后」才触发的，所以 model / tool span 是**事后 `record`**，彼此是兄弟而不是「tool 嵌在 model 里」。这棵扁平树对排障已经够用。如果你想画出严格嵌套，改用 `async with trace.span(...)` 把 `run_task` 里的每段包起来（步骤 6 的 OTel 版就是这种）。

### 步骤 6：把 `trace_id` 透传到 App（改 2 行）

一期 `server/api.py` 的 `done` 事件加一个字段即可，**不破坏协议**：

```python
# 在 event_stream() 里，hooks 已经是 TracingHooks 实例
yield {"data": json.dumps({
    "type": "done",
    "usage": last_usage(),
    "trace_id": hooks.trace.trace_id,     # ← 新增这一行
}, ensure_ascii=False)}
```

同时把接口层改成用统一入口（一次性对齐，后面模块都受益）：

```python
from server.base import run_task
from server.observability import TracingHooks

# 在 event_stream() 内，替换原来直接调 graph 的段落（MVP 阶段可先只加 trace，不换图）
hooks = TracingHooks(req.message, req.thread_id)
# 若你暂时仍用 graph.astream，也请至少在 done 事件里带上 hooks.trace.trace_id，
# 并在流结束时调用 await hooks.on_end(result) 落盘。
```

**为什么 App 不会崩**：一期 `AgentRepository.kt` 的 `when (json.optString("type"))` 只匹配 `done`，`optJSONObject("usage")` 之外多一个未知字段会被 `JSONObject` 直接忽略——和 Gson / Moshi 解析 JSON 时忽略未知字段是同一个行为。所以后端可以安全地加字段，前端不用同步改。

> 想让 App 显示「本次 trace id」以便用户报障时贴给你？在 `ChatEvent.Done` 加一个 `traceId: String?` 字段即可，留作练习。

### 步骤 7（可选）：换成生产导出器

教学版 JSONL 和 OpenTelemetry 的 span 模型一一对应：**业务代码不动，只换导出器**。

**OpenTelemetry（自托管 / OTLP）**：

```python
# server/observability_otel.py（示意，替换 TracingHooks 内部实现即可）
from opentelemetry import trace as otel
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))   # 本地先打控制台
# provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")))
otel.set_tracer_provider(provider)
tracer = otel.get_tracer("agent-learning")

with tracer.start_as_current_span("agent.run") as root:
    with tracer.start_as_current_span("llm.call") as sp:
        sp.set_attribute("llm.tokens", 248)
        sp.set_attribute("llm.model", "qwen-plus")
```

对应平台（2026 常用，选一个即可）：

| 平台 | 安装 | 特点 |
| --- | --- | --- |
| Langfuse | `uv add langfuse` | 开源可自托管，LLM 语义最贴合 |
| LangSmith | `uv add langsmith` + 环境变量 | LangGraph 集成最深 |
| Arize Phoenix | `uv add arize-phoenix` | 内置评估指标多 |
| Jaeger / Grafana Tempo | 走 OTLP | 已有可观测基建的团队复用 |

配好 `.env` 后把 `TracingHooks` 的 `on_model` 里加一行 `langfuse.trace(...).span(...)` 即可。**不要同时维护两套**：先跑通 JSONL，选定平台后一次性替换 `save()`。

---

## 4. 常见报错与修复

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| `usage` 全是 0 | 平台在非流式响应里没给 `usage`，或字段叫 `usage_metadata` | 先 `print(data.keys())` 看原始响应；流式模式加 `"stream_options": {"include_usage": true}` 并取最后一个 chunk |
| `ModuleNotFoundError: server` | 没在仓库根目录跑，或缺 `__init__.py` | 在 `agent-learning/` 根目录执行；补 `server/__init__.py` |
| `python -m eval.view_trace` 报 `No module named eval` | 缺 `eval/__init__.py` | 步骤 1 补上 |
| trace 文件的中文是 `\u...` | `json.dumps` 默认转义 | 代码里已用 `ensure_ascii=False` |
| 并发两个请求，span 父亲错乱 | 把 `Trace` 做成了全局单例 | 保持「每请求一个实例」；如需跨函数传递用 `contextvars.ContextVar` |
| JSONL 单行几 MB | 工具返回没截断 | `out[:500]`，见 `on_tool`；P0-03 会做更系统的瘦身 |
| `TracingHooks` 报缺 `on_tool` 第 5 个参数 | `run_task` 是早期 4 参数版本 | 确认 `run_task` 里调用的是 `await hooks.on_tool(name, args, out, turn, tool_ms)`，即带 `tool_ms` 的 5 参数版（README §4.3 已是此版） |
| trace 目录没生成 | 工作目录不对 | `TRACE_DIR` 用相对路径，务必在仓库根跑；或设 `TRACE_DIR` 为绝对路径 |

---

## 5. 必做实验：用 trace 抓死循环

一期第 5 周讲了四大失败模式，其中「死循环」当时只能靠 `MAX_TURNS` 兜住。现在用 trace 把它**看见**：

1. 临时把 `scripts/demo_tools.py` 的 `fake_weather` 改成永远失败：

```python
def fake_weather(city: str) -> str:
    return "错误：天气服务暂时不可用"      # 模型会反复重试
```

2. 临时把 `server/base.py` 的 `MAX_TURNS` 改成 `3`，跑：

```powershell
uv run python scripts/try_trace.py "苏州今天多少度"
uv run python -m eval.view_trace
```

3. 观察输出：连续 3 个 `llm.*` span + 3 个 `tool.get_weather` span，`status=error`，root 上 `turns=3`、`error=达到最大轮次 3 仍未完成`。

**对照体验**：平铺日志你只能看到 3 行相似文本；trace 树里「同一工具、同一参数、连续重复」是一个肉眼可辨的视觉模式，还能直接读出每次耗时和累计 token。这就是 P0-04 要加「重复调用检测」护栏的依据。

实验完把 `fake_weather` 和 `MAX_TURNS` 改回去，然后：

```powershell
git add server/observability.py eval/view_trace.py scripts/ && git commit -m "P0-01: add tracing spans for model/tool calls"
```

---

## 6. 验收自测

- [ ] `uv run python scripts/try_trace.py` 跑通，生成 `eval/traces/*.jsonl`
- [ ] `uv run python -m eval.view_trace` 能打印完整调用树，含耗时 / token / 成本
- [ ] trace 里能看到每一次模型调用和每一次工具调用，一个不漏
- [ ] 死循环实验完成，trace 中能指出「哪一步开始重复、重复了几次、烧了多少 token」
- [ ] `/api/chat` 的 `done` 事件带上 `trace_id`，App 端未报错
- [ ] 能口头解释 `trace_id` 与 `thread_id` 的区别
- [ ] 代码提交 git，`NEXT.md` 增加一行「现象 → 指标变化 → commit」

**自测题**：

1. 为什么 `Trace` 不能做成全局单例？如果做成全局的，FastAPI 同时处理两个会话时具体会错成什么样？
2. `on_tool` 里为什么要截断结果到 500 字符？这和一期的哪个知识点是同一条原则？
3. 假设某个工具执行抛了异常，`run_task` 把异常当字符串回填。trace 里这个 span 的 `status` 应该是什么？为什么不能让进程崩掉？
4. 后端给 `done` 事件加 `trace_id` 为什么不需要同步改安卓端？这利用了 JSON 解析的什么特性？

---

## 7. 衔接 P0-02

现在每次运行都留下了一份结构化记录：轮次、工具调用序列（含参数）、每步耗时、token、成本、错误类型、最终回答。

**P0-02 就不需要重新造数据采集了**——评估器直接读 `AgentResult` 和 `trace`，把一期那张人工填的 `eval/results.md` 变成一条命令自动生成的报告，再挂到 CI 上当门禁。下一步见 `P0-02-自动化评估与CI门禁.md`。
