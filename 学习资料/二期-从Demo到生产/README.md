# 二期：从 Demo 到生产（三条纵线实战）

> 配套《Agent 开发学习计划》一期 12 周。一期交付的是**能演示的作品集**，二期交付的是**能交付的系统**。
>
> 二期不再按周线性上课，改成 **backlog 驱动**：每个模块解决一个真实问题，落到「一个可运行 commit + 一条评估指标变化」。任何新知识没有落到这两样东西上，就不算学会。

---

## 0. 开始之前：先做结业体检

你说「假设学完了」，但大多数人「学完」其实只是「读完」。开始二期前，拿一期第 12 周的验收清单逐条打勾：

| # | 硬指标 | 不达标回哪份资料 |
| --- | --- | --- |
| 1 | 3 个场景真机可用，全链路「输入 → 调工具 → 流式返回」跑通 | 第 11 周 |
| 2 | 陌生人 clone 仓库后 5 分钟内能跑起来 | 第 12 周 README 章节 |
| 3 | `eval/results.md` 有 10 任务数据 + 至少 1 个「失败 → 归因 → 修复 → 重跑」闭环 | 第 12 周 |
| 4 | 对着架构图 10 分钟讲清整个系统，不卡壳 | 第 10、12 周 |
| 5 | 能回答「框架替我做了什么 / 协议替我做了什么 / 哪里仍离不开底层理解」 | 第 12 周复盘 |

**五条全勾再往下走。** 二期所有代码都建立在「你有一个能跑的 Agent」之上；如果它现在还跑不起来，先回去修，不要带着一个坏基线往前堆功能。

---

## 1. 二期解决什么问题

一期结束时的你，能力是完整的：手写循环、LangGraph 编排、Checkpointer/interrupt、MCP、FastAPI + SSE + 安卓端到端、10 任务人工评估、token 统计。但项目状态是**「能演示的 demo」**，不是**「能交付的系统」**。

2026 年的行业现实很直白：主流编排框架已经收敛（LangGraph 是生产标准，你学的正是它），MCP + A2A 在 Linux Foundation 下形成「纵向工具 / 横向协作」的分层标准；但约六成团队仍停在试点，只有一成左右真正规模化。**卡点不是少学了一个框架，而是治理、评估、可观测性、成本与安全。**

所以二期的定位是：

> **不横向铺新框架，不囤新教程。把同一个项目纵向做深、做稳、讲清楚。**

一句话对照：`第 6 周手写循环` 给你的是判断力，二期给你的是**把判断力放进生产环境还活得住的工程能力**。

---

## 2. 三条纵线与优先级

| 纵线 | 模块 | 产出 | 优先级 |
| --- | --- | --- | --- |
| **P0 生产化深挖** | P0-01 可观测性 Tracing | 每次运行的完整执行树 | **必做，最先做** |
| | P0-02 自动化评估与 CI 门禁 | eval 套件 + 不过门禁不许合并 | **必做** |
| | P0-03 上下文工程与成本工程 | token 降 40%+ 且完成率不掉 | **必做** |
| | P0-04 安全护栏与部署版本化 | 最小权限 / 注入防护 / Docker / CI | **必做** |
| **P1 能力扩展** | P1-01 RAG 检索自己的笔记 | 第 4 个场景 + MCP 工具 | 三选一 |
| | P1-02 Supervisor 分层多 Agent | 3 个场景拆成 planner + specialist | 三选一 |
| | P1-03 框架对比式学习与文章 | 对比文章 + 简历亮点 | 方法论，随时可做 |
| **P2 协议补全** | P2-01 A2A 协议最小实现 | Agent Card + Task 状态机 + 委派 | 选做（走 P1-02 则必做） |
| | P2-02 MCP 与 A2A 分层架构 | 分布式架构图 + 端到端演示 | 接 P2-01 |

**推荐顺序**：

```
结业体检 → 0 号补丁 → P0-01 → P0-02 → P0-03 → P0-04 →（P1 三选一）→（P2）→ 作品集升级
```

理由：P0-01 的 trace 是 P0-02 评估的数据源，P0-02 的 eval 是 P0-03 优化能否「用数据说话」的判据，P0-03 的上下文/成本结论又决定 P0-04 的护栏阈值。**这四个是一串，不要打乱。**

P1 只挑一个做深（3 个做深比 10 个做浅有价值，一期第 12 周原话）。P2 不是换框架，是把第 9 周 MCP 的知识补完整。

### 闸门：什么时候才学第二个框架

只有两种情形打开：① 目标岗位 JD 明确写了；② 你带着一个 LangGraph 表达得很别扭的**具体问题**。

打开后也**不要从头看教程**——用 1~2 天把现有项目的一个场景在第二个框架上重写，然后写对比文章。具体做法见 `P1-03-框架对比式学习与文章.md`。

---

## 3. 全局约定

### 3.1 沿用一期（不要改）

- Python 3.11+，包管理用 `uv`
- 代码仓库仍是 `agent-learning`，目录按周组织（`week01/`…`week12/`）
- **二期所有代码加在同一个仓库里，不新建仓库**
- 模型接口一律 OpenAI 兼容模式，`.env` 里 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- API Key 放 `.env`，`.gitignore` 必须含 `.env`
- 每完成一个可运行增量就 `git commit`

### 3.2 二期新增环境变量（写进 `.env.example`，不要写进 `.env` 提交）

| 变量 | 用途 | 默认 | 用到它的模块 |
| --- | --- | --- | --- |
| `LLM_MODEL_FAST` | 便宜模型，用于分类/路由/摘要 | 同 `LLM_MODEL` | P0-03 |
| `LLM_EMBED_MODEL` | 嵌入模型名 | `text-embedding-v3` | P1-01 |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | 可选，云端 trace | 不配则只写本地文件 | P0-01 |
| `AGENT_AUTONOMY_LEVEL` | `shadow` / `assist` / `autonomy` | `assist` | P0-04 |
| `A2A_BASE_URL` | Specialist Agent 地址 | `http://127.0.0.1:9001` | P2-01 |
| `EVAL_THRESHOLD` | CI 门禁阈值覆盖 | 用 `eval/thresholds.yaml` | P0-02 |

### 3.3 二期新增依赖（按模块装，别一次性全装）

| 模块 | 命令 |
| --- | --- |
| 0 号补丁 | `uv add httpx python-dotenv pydantic` |
| P0-01 | `uv add opentelemetry-api opentelemetry-sdk` （可选 `uv add langfuse`） |
| P0-02 | `uv add pyyaml pytest` |
| P0-03 | 无新增（用标准库 + 一期依赖） |
| P0-04 | `uv add pyyaml` （Docker 不需要 Python 包） |
| P1-01 | `uv add chromadb numpy` （或走「无向量库」备选） |
| P1-02 | 无新增（LangGraph 已有） |
| P2-01 / 02 | `uv add fastapi uvicorn httpx` （已有） |

### 3.4 仓库侧目标目录

```
agent-learning/
├── server/                     # 一期已有：FastAPI 后端
│   ├── api.py                  # 第 11 周 SSE 接口
│   ├── agent.py                # 第 7~8 周 build_app()
│   ├── llm.py                  # 第 4 周裸 httpx 封装
│   ├── base.py                 # ★ 二期 0 号补丁（本文件 §4）
│   ├── observability.py        # ★ P0-01
│   ├── context.py              # ★ P0-03
│   ├── cost.py                 # ★ P0-03
│   ├── guardrails.py           # ★ P0-04
│   ├── rag/                    # ★ P1-01
│   ├── multi/                  # ★ P1-02
│   ├── a2a/                    # ★ P2-01 / P2-02
│   └── mcp_servers/
│       └── agenda_server.py    # 一期第 9/12 周
├── eval/
│   ├── tasks.json              # 一期第 12 周，10 个任务
│   ├── results.md              # 一期第 12 周
│   ├── base.py                 # ★ P0-02 统一入口
│   ├── run_eval.py             # ★ P0-02
│   ├── graders.py              # ★ P0-02
│   ├── thresholds.yaml         # ★ P0-02
│   └── traces/                 # ★ P0-01 本地 trace（JSONL）
├── configs/
│   └── agent.yaml              # ★ P0-04 prompt / model / tool 版本化
├── .github/workflows/eval.yml  # ★ P0-02
├── Dockerfile / compose.yaml   # ★ P0-04
├── NEXT.md                     # ★ 二期 backlog
└── README.md / RETRO.md        # 一期已有，二期持续更新
```

### 3.5 教程侧目录（本文件夹）

| 文件 | 纵线 | 主题 |
| --- | --- | --- |
| `README.md` | — | 本文件：总纲与基线契约 |
| `P0-01-可观测性Tracing.md` | P0 | 给 Agent 装上黑匣子 |
| `P0-02-自动化评估与CI门禁.md` | P0 | 从「感觉能用」到「数据说话」 |
| `P0-03-上下文工程与成本工程.md` | P0 | 把 token 当预算管 |
| `P0-04-安全护栏与部署版本化.md` | P0 | 最小权限、注入防护、灰度 |
| `P1-01-RAG检索自己的笔记.md` | P1 | 把 12 周笔记做成知识库 |
| `P1-02-Supervisor分层多Agent.md` | P1 | planner + specialist |
| `P1-03-框架对比式学习与文章.md` | P1 | 第二框架的正确学法 |
| `P2-01-A2A协议最小实现.md` | P2 | Agent Card 与 Task 生命周期 |
| `P2-02-MCP与A2A分层架构.md` | P2 | 纵向工具 / 横向协作 |

---

## 4. 基线代码契约（动手前必读，最重要的一节）

二期 9 个模块全部依赖**同一组契约**。先花 30 分钟把一期代码对齐到下面这个 `server/base.py`，后面每个模块都只需要「加一个新文件 + 改 2~3 行」，不会互相打架。

### 4.1 一期结束时你应有的四个契约面

| 契约面 | 一期的样子 | 二期要求 |
| --- | --- | --- |
| 模型调用 | `server/llm.py` 里 `call_model(...)` 返回 message dict | 统一返回 `ModelResponse`（含 `usage`） |
| 图构建 | `server/agent.py::build_app()` 返回编译后的图（带 SqliteSaver） | 不变，签名不变 |
| HTTP 接口 | `POST /api/chat` → SSE，事件 `delta` / `tool_call` / `interrupt` / `done` / `error` | 不变，二期只在事件里加字段 |
| 评估集 | `eval/tasks.json`，字段 `id / scene / input / expect / type` | 不变，二期加 `graders` 字段 |

**如果你的一期代码和上面不完全一样**：不用重写，只要保证 `build_app()` 和 `/api/chat` 这两个对外契约不变，内部随便改。二期插桩一律走 `base.py`，不碰你的核心循环。

### 4.2 「0 号补丁」：`server/base.py`

新建这个文件，它是二期所有模块的公共地基。作用：把模型调用统一成带 `usage` 的返回对象，并提供一个统一的 `run_task()` 入口，让后面的 tracing / eval / 成本统计有唯一的挂载点。

```python
"""server/base.py —— 二期公共契约。所有二期模块只依赖本文件，不改一期核心循环。"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["LLM_BASE_URL"]
KEY = os.environ["LLM_API_KEY"]
MODEL = os.environ["LLM_MODEL"]
MODEL_FAST = os.environ.get("LLM_MODEL_FAST", MODEL)

# 单价表：按「元 / 千 token」填你自己平台的实际价格，只用于估算，不用于计费
PRICE_PER_1K = {
    "input": 0.004,
    "output": 0.012,
}


@dataclass
class ModelResponse:
    """一次模型调用的完整结果。一期只返回 message，二期开始必须带上 usage。"""
    message: dict
    usage: dict = field(default_factory=dict)
    latency_ms: float = 0.0
    model: str = ""

    @property
    def tool_calls(self) -> list[dict]:
        return self.message.get("tool_calls") or []

    @property
    def content(self) -> str:
        return self.message.get("content") or ""


@dataclass
class AgentResult:
    """一次 Agent 运行的统一结果。P0-01 起所有模块都产出它。"""
    task: str
    thread_id: str
    answer: str = ""
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"prompt_tokens": 0,
                                                 "completion_tokens": 0,
                                                 "total_tokens": 0})
    latency_ms: float = 0.0
    trace_id: str = ""
    error: str | None = None


def estimate_cost(usage: dict) -> float:
    """按单价表估算一次调用成本（元）。"""
    p = usage.get("prompt_tokens", 0) / 1000 * PRICE_PER_1K["input"]
    c = usage.get("completion_tokens", 0) / 1000 * PRICE_PER_1K["output"]
    return round(p + c, 6)


def merge_usage(total: dict, one: dict) -> dict:
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        total[k] = total.get(k, 0) + (one.get(k) or 0)
    return total


async def call_model(
    messages: list[dict],
    tools: list[dict] | None = None,
    *,
    model: str | None = None,
    temperature: float = 0.2,
) -> ModelResponse:
    """统一模型调用。OpenAI 兼容接口，返回 message + usage + 延迟。"""
    use_model = model or MODEL
    payload: dict[str, Any] = {
        "model": use_model,
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    t0 = time.perf_counter()
    resp = await httpx.AsyncClient(timeout=60).post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {KEY}"},
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    latency = (time.perf_counter() - t0) * 1000

    return ModelResponse(
        message=data["choices"][0]["message"],
        usage=data.get("usage", {}),
        latency_ms=round(latency, 2),
        model=use_model,
    )
```

**验收动作**（做完这一步就 commit，别往后拖）：

```powershell
uv run python -c "import asyncio; from server.base import call_model; r=asyncio.run(call_model([{'role':'user','content':'说三个字'}])); print(r.content, r.usage, r.latency_ms)"
```

预期：打印出回答、`{'prompt_tokens': ..., 'completion_tokens': ..., 'total_tokens': ...}`、一个毫秒数。**`usage` 为空说明你的平台在流式/非流式下字段位置不同**，按 `P0-01` 踩坑表处理。

### 4.3 统一运行入口（P0-01 会在这里插桩）

在 `server/base.py` 末尾追加 `run_task()`。它复刻第 6 周那个 while 循环，但返回 `AgentResult`。二期所有模块都调用它，**不再直接调 `call_model`**：

```python
SYSTEM = """你是一个任务执行 Agent。规则：
1. 需要事实数据（天气、笔记、日程）时必须先调用工具获取，禁止编造。
2. 数学计算必须用 calculator，禁止心算。
3. 拿到足够信息后立即给出最终答案，不要多余的工具调用。"""
MAX_TURNS = 10


async def run_task(
    task: str,
    *,
    thread_id: str | None = None,
    tools: list[dict] | None = None,
    tool_funcs: dict | None = None,
    model: str | None = None,
    hooks: Any = None,               # P0-01 传入 tracer；其余模块透传
    context_policy: Any = None,      # P0-03 传入：async (messages) -> messages
) -> AgentResult:
    """统一 Agent 运行入口：第 6 周循环 + 统一结果对象。"""
    import asyncio
    import json

    tid = thread_id or uuid.uuid4().hex
    result = AgentResult(task=task, thread_id=tid, trace_id=uuid.uuid4().hex)
    history: list[dict] = [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": task}]
    t0 = time.perf_counter()

    try:
        for turn in range(1, MAX_TURNS + 1):
            if context_policy:
                history = await context_policy(history)   # P0-03 插桩点，默认 None
            r = await call_model(history, tools, model=model)
            merge_usage(result.usage, r.usage)
            if hooks:
                await hooks.on_model(r, turn)        # P0-01 的插桩点

            if not r.tool_calls:
                result.answer = r.content
                result.messages = history
                break

            history.append({"role": "assistant", "content": r.content,
                            "tool_calls": r.tool_calls})
            for tc in r.tool_calls:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                result.tool_calls.append({"turn": turn, "name": name, "args": args})
                t_tool = time.perf_counter()
                try:
                    fn = (tool_funcs or {}).get(name)
                    if fn is None:
                        out = f"错误：未知工具 {name}"
                    else:
                        out = fn(**args)
                        if asyncio.iscoroutine(out):
                            out = await out
                    out = str(out)
                except Exception as e:              # 一期护栏：异常回填，不崩进程
                    out = f"工具执行异常: {type(e).__name__}: {e}"
                tool_ms = round((time.perf_counter() - t_tool) * 1000, 2)
                if hooks:
                    await hooks.on_tool(name, args, out, turn, tool_ms)
                history.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
        else:
            result.error = f"达到最大轮次 {MAX_TURNS} 仍未完成"
            result.answer = "（任务未完成，已产生的信息见 trace）"
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        result.answer = ""
    finally:
        result.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        if hooks:
            await hooks.on_end(result)

    return result
```

`hooks` 是二期唯一的可扩展点，接口固定为三个异步方法（P0-01 提供实现，其余模块透传）：

```python
class Hooks:
    async def on_model(self, r: ModelResponse, turn: int) -> None: ...
    async def on_tool(self, name: str, args: dict, out: str,
                      turn: int, elapsed_ms: float) -> None: ...
    async def on_end(self, result: AgentResult) -> None: ...
```

对照安卓理解这份契约：`ModelResponse` ≈ 一次 `Result<T>` 包装，`AgentResult` ≈ 整个用例的执行报告，`hooks` ≈ OkHttp 的 `Interceptor`——**业务代码不变，只在关键节点挂观察者**。这正是二期能「不改核心循环就把可观测性/评估/成本全加上」的原因。

`run_task` 里 `context_policy` 的插桩点（循环里那一行）也已预留，P0-03 只需实现策略函数并传进来，**不需要再改 `run_task`**。所以请务必照上面这份最新代码建 `server/base.py`，后面 9 个模块都假定这两个插桩点存在。

---

## 5. 每个模块的统一结构

二期 9 个模块都按同一套结构写，方便你按顺序推进：

1. **学习目标** —— 3~5 条，可勾选
2. **为什么要做（对照安卓）** —— 先讲痛点，再给类比
3. **逐步操作** —— 编号步骤，每条都给完整命令、文件路径、预期输出
4. **完整可运行代码** —— 能直接粘贴，不是伪代码骨架
5. **常见报错与修复** —— 表格，含「现象 → 原因 → 修复」
6. **验收自测** —— checkbox + 自测题
7. **衔接下一模块** —— 说明本模块的产出下个模块怎么用

**每完成一个模块，做三件事**：跑通验收自测 → 更新 `NEXT.md` 的指标行 → `git commit`。

---

## 6. 学习法：backlog 驱动

一期是「按周上课」，二期是「问题驱动」。在仓库根新建 `NEXT.md`：

```markdown
# 二期 backlog

| 状态 | 问题（现象） | 假设 | 实验 | 指标变化 | commit |
| --- | --- | --- | --- | --- | --- |
| doing | 无解任务偶发死循环，但说不清哪一步坏的 | 缺执行轨迹 | 接 tracing | 失败定位时间 15min → 2min | a1b2c3 |
| todo | 改了 prompt 后完成率好像掉了 | 没有回归门禁 | eval 进 CI | 完成率可量化、回归可拦截 | — |
```

**硬规则**：

- 每个新知识必须落到「一个可运行 commit」或「一条评估指标变化」，否则不算学会
- 不为了「再学一个」而加功能；3 个场景做深比 10 个做浅有价值
- 卡住时查官方文档，不囤教程（一期 README 三条纪律，二期继续生效）
- 每模块结束写 3~5 行 `NOTES.md`：现象 → 原因 → 修复，累积成作品集的「踩坑记录」

提交信息建议：`P0-01: add tracing spans for model/tool calls`，一条 commit 对应一个可验证增量。

---

## 7. 总验收清单

### P0（必做，全部打勾才算二期合格）

- [ ] 每次运行都有完整 trace：模型调用 / 工具调用 / token / 延迟 / 错误，能回答「哪一步坏了」
- [ ] `uv run python -m eval.run_eval` 一键跑完全部任务，输出指标表
- [ ] CI 门禁生效：故意改坏一个 prompt 建 PR，能拦住合并
- [ ] 上下文/成本优化后有前后对比数据：token 明显下降且完成率不掉
- [ ] 安全用例（含 prompt injection）进 eval 集且全部通过
- [ ] `docker compose up` 一条命令起后端，`.env` 不进镜像
- [ ] `configs/agent.yaml` 版本化 prompt / model / tool schema，能回滚

### P1 / P2（按选择打勾）

- [ ] P1 选定方向做深，产出第 4 个场景或分层多 Agent，并有评估数据
- [ ] （若学第二框架）产出对比文章，而非「又学完一个框架」
- [ ] （若走 P2）Agent Card 可发现、Task 生命周期可查、委派链路端到端跑通
- [ ] 架构图升级，README 增加「可观测性 / 评估 / 成本 / 安全」四个章节
- [ ] 简历 3 行亮点 + 10 分钟讲法更新，能从「架构 → 数据流 → 评估 → 踩坑 → 生产化」讲完整

### 最终交付物

一个**别人 clone 下来 5 分钟能跑、改一行 prompt 会被 CI 拦住、出问题能看 trace、烧钱有上限、危险操作有人把关**的 Agent 系统。这才是「能交付」，而不是「能演示」。

---

## 8. 开始

按 `§4` 做完 0 号补丁并 commit，然后打开 `P0-01-可观测性Tracing.md`。

> 一期的终点是让你能说「框架在替我做我写过的那个循环」。二期的终点是让你能说「这个系统我敢放到生产环境，并且我知道它每一分钱、每一步、每一次失败是怎么发生的」。
