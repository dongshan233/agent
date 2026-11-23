# P1-01 RAG：把 12 周笔记做成自己的知识库

> P1 能力扩展 · 三选一方向 A。**前置**：P0 四个模块（尤其 P0-02 门禁、P0-03 上下文预算）。
> 目标：把你自己这 12 周教程变成可检索的知识库，作为第 4 个场景接进 Agent，并**复用第 9 周的 MCP** 暴露出去。

## 学习目标

1. 走通 RAG 全链路：分块 → 嵌入 → 向量检索 → 组装上下文 → 带引用生成
2. 会设计中文 Markdown 的分块策略与 metadata
3. 把检索能力做成 MCP Server（而不是塞进 Agent 代码）
4. 把「检索质量」和「生成质量」隔离评估，不混为一谈
5. 用 P0-02 门禁验证新场景没有让原有 15 条用例退步

---

## 1. 为什么选这个方向（对照安卓）

三个 P1 方向里，RAG 对你**闭环最快、最私人**：语料就是你这 12 周亲手敲过的笔记，不用找数据；做出来的东西自己每天能用；还能顺手把第 9 周的 MCP 和第 12 周的作品集串起来。

对照安卓：

| 安卓 | RAG |
| --- | --- |
| Room + FTS4 全文检索 | 向量检索（语义匹配，不靠关键词相同） |
| 建索引 / 增量更新 | ingest 脚本 + 持久化索引 |
| `Cursor` 分页查询 | top-k 检索 + 重排 |
| 列表只渲染可见项 | 只把命中的 chunk 塞进上下文（上下文预算！） |
| 详情页带来源 ID | 回答带引用锚点 `[1] 05-第5周…` |

**关键心智模型**：RAG 不是「给模型外挂数据库」，而是**上下文工程的一种**——在每一次调用前，动态决定「这次该让模型看到哪几段资料」。P0-03 讲的最小可信信息，RAG 是它的自动化实现。

### 什么时候 RAG 会失败（先知道，少踩坑）

| 失败 | 现象 | 归属 |
| --- | --- | --- |
| 检索没命中 | 相关文档存在但没被取出来 | **检索问题** |
| 取到了过期/矛盾版本 | 答案引用了旧笔记 | 检索问题 |
| 命中了但模型没用 | 回答编造，不引用 | 生成问题 |
| chunk 切碎了代码块 | 代码示例残缺 | 分块问题 |

**最重要的工程原则**：把检索质量和生成质量**分开测**。检索命中率不够就去调 chunk / top-k / embedding，别急着改 prompt——这是 2026 年 RAG 调试最常见的浪费。

---

## 2. 概念：一次 RAG 的数据流

```
离线（跑一次）
  12 周 .md ──分块──→ chunks[] ──/embeddings──→ vectors ──→ 持久化索引

在线（每次提问）
  用户问题 ──embed──→ 查询向量 ──top-k 检索──→ hits[]
      │
      ├── 检索评估：Recall@k（不看生成，先验命中）
      │
      └── 组装上下文（带来源锚点、控制总长度）
              │
              ▼
          Agent 生成回答（要求引用 [1][2]）
```

**为什么走 MCP**：第 9 周你已经把「笔记查询」做成了 `notes_server.py` 的 stdio Server。现在把它升级成 RAG 版——**Agent 侧一行不用改**，只是工具实现从「关键词 grep」换成了「语义检索」。这就是协议化的回报，也是面试里很值得讲的一句：「我把检索能力换了一代，编排层无感知。」

---

## 3. 逐步操作

### 步骤 1：装依赖

```powershell
uv add chromadb numpy
mkdir -p server/rag eval/rag_index
New-Item -ItemType File server/rag/__init__.py
```

`.env` 追加（**二期的全局约定里已列过**）：

```
LLM_EMBED_MODEL=text-embedding-v3
NOTES_DIR=E:/study/agent/学习资料
```

> 平台兼容提醒：国内百炼 / DeepSeek / OpenAI 的 `/embeddings` 接口基本兼容，但**模型名和维度各家不同**。先跑步骤 3 的 `probe_embed.py` 确认，别直接照抄模型名。

### 步骤 2：先探一下嵌入接口（5 分钟，避免后面全白做）

`scripts/probe_embed.py`：

```python
"""scripts/probe_embed.py —— 确认平台的 /embeddings 能用、维度多少。"""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
BASE, KEY = os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"]
MODEL = os.getenv("LLM_EMBED_MODEL", "text-embedding-v3")


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"{BASE}/embeddings",
            headers={"Authorization": f"Bearer {KEY}"},
            json={"model": MODEL, "input": ["Agent 是什么", "上下文工程"]},
        )
        print("status", r.status_code)
        print(r.text[:400])
        if r.status_code == 200:
            d = r.json()["data"]
            print("维度 =", len(d[0]["embedding"]), " 条数 =", len(d))


asyncio.run(main())
```

```powershell
uv run python scripts/probe_embed.py
```

预期：`status 200`、`维度 = 1024`（或你平台的值）、`条数 = 2`。**记下维度**，换 embedding 模型必须重建索引（见踩坑表）。

若平台没有 `/embeddings`，走步骤 6 的「无嵌入模型备选」。

### 步骤 3：`server/rag/ingest.py`（分块 + 建索引）

```python
"""server/rag/ingest.py —— 把一期 12 周笔记做成向量索引。
运行: uv run python -m server.rag.ingest
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

import chromadb
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["LLM_BASE_URL"]
KEY = os.environ["LLM_API_KEY"]
EMBED_MODEL = os.getenv("LLM_EMBED_MODEL", "text-embedding-v3")
NOTES_DIR = Path(os.getenv("NOTES_DIR", "E:/study/agent/学习资料"))
INDEX_DIR = Path("eval/rag_index")
COLLECTION = "course_notes"

# 只索引一期的 12 周教程 + README，避免把二期教程自己混进去造成自指
INCLUDE = re.compile(r"^(README|\d{2}-第\d+周-.*)\.md$")

MAX_CHARS = 900          # 中文约 1 字 ≈ 1~2 token，900 字 ≈ 1200~1800 token
OVERLAP = 120            # 相邻块重叠，防边界切断语义


def split_markdown(path: Path) -> list[dict]:
    """按 ## / ### 标题切块；标题层级作为 heading 路径保留进 metadata。

    为什么不按固定字数硬切：会把代码块、表格、消息流转图切碎，
    检索出来的是半截代码，模型没法用。按 Markdown 结构切是中文教程语料
    最省事且效果最好的策略。
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    chunks: list[dict] = []
    h2 = h3 = ""
    buf: list[str] = []

    def flush():
        body = "\n".join(buf).strip()
        if len(body) < 40:               # 太短的小节并入下一块
            return
        heading = " › ".join(x for x in (h2, h3) if x)
        # 超长块再按段落二次切（带 overlap）
        if len(body) <= MAX_CHARS:
            pieces = [body]
        else:
            pieces, cur = [], ""
            for para in body.split("\n\n"):
                if len(cur) + len(para) > MAX_CHARS and cur:
                    pieces.append(cur)
                    cur = cur[-OVERLAP:] + "\n\n" + para
                else:
                    cur = (cur + "\n\n" + para).strip()
            if cur:
                pieces.append(cur)
        for i, piece in enumerate(pieces):
            chunks.append({
                "id": f"{path.stem}::{len(chunks)}",
                "text": f"[{path.stem}] {heading}\n{piece}" if heading else piece,
                "metadata": {
                    "source": path.name,
                    "heading": heading or "全文",
                    "part": i,
                    "week": path.stem[:2],
                },
            })
        buf.clear()

    for line in lines:
        if line.startswith("## "):
            flush()
            h2, h3 = line[3:].strip(), ""
        elif line.startswith("### "):
            flush()
            h3 = line[4:].strip()
        elif line.startswith("# "):
            continue
        else:
            buf.append(line)
    flush()
    return chunks


async def embed(texts: list[str]) -> list[list[float]]:
    """批量调 /embeddings。批量是为了省钱省延迟，别一条一条调。"""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{BASE}/embeddings",
            headers={"Authorization": f"Bearer {KEY}"},
            json={"model": EMBED_MODEL, "input": texts},
        )
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d.get("index", 0))
        return [d["embedding"] for d in data]


async def build_index() -> int:
    files = sorted(p for p in NOTES_DIR.glob("*.md") if INCLUDE.match(p.name))
    chunks = [c for p in files for c in split_markdown(p)]
    print(f"扫描 {len(files)} 个文件 → {len(chunks)} 个 chunk")

    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    col = client.get_or_create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    BATCH = 16
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        vectors = await embed([c["text"] for c in batch])
        col.upsert(
            ids=[c["id"] for c in batch],
            embeddings=vectors,
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )
        print(f"  indexed {min(i + BATCH, len(chunks))}/{len(chunks)}")
    return len(chunks)


if __name__ == "__main__":
    n = asyncio.run(build_index())
    print(f"完成，共 {n} 个 chunk，索引目录 {INDEX_DIR}")
```

```powershell
uv run python -m server.rag.ingest
```

预期：`扫描 13 个文件 → 2xx 个 chunk`，逐批打印进度。**先人工抽查两个 chunk**：

```powershell
uv run python -c "import chromadb; c=chromadb.PersistentClient(path='eval/rag_index').get_collection('course_notes'); print(c.get(limit=2, include=['documents','metadatas']))"
```

看代码块有没有被切断、heading 路径对不对。分块质量决定 RAG 上限，这一步别省。

### 步骤 4：`server/rag/retrieve.py`（检索 + 带引用组装）

```python
"""server/rag/retrieve.py —— 检索与上下文组装。"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv

from server.rag.ingest import COLLECTION, INDEX_DIR, embed

load_dotenv()
MAX_CONTEXT_CHARS = int(os.getenv("RAG_MAX_CONTEXT", "3500"))   # 上下文预算，P0-03 原则


def _collection():
    client = chromadb.PersistentClient(path=str(INDEX_DIR))
    return client.get_collection(COLLECTION)


async def search(query: str, top_k: int = 4) -> list[dict]:
    """语义检索，返回带来源与相似度分数的命中。"""
    q_vec = (await embed([query]))[0]
    res = _collection().query(
        query_embeddings=[q_vec],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0],
                               res["distances"][0]):
        hits.append({
            "text": doc,
            "source": meta["source"],
            "heading": meta["heading"],
            "week": meta["week"],
            "score": round(1 - dist, 4),       # cosine 距离 → 相似度
        })
    return hits


def format_context(hits: list[dict]) -> str:
    """组装带引用锚点的上下文，并受 MAX_CONTEXT_CHARS 硬预算约束。"""
    parts, used = [], 0
    for i, h in enumerate(hits, 1):
        block = f"[{i}] {h['source']} › {h['heading']}\n{h['text']}"
        if used + len(block) > MAX_CONTEXT_CHARS:
            break
        parts.append(block)
        used += len(block)
    header = ("以下是从课程笔记检索到的资料。回答时必须用 [1][2] 标注来源；"
              "资料中没有的内容不要编造。\n\n")
    return header + "\n\n---\n\n".join(parts)


async def demo(query: str) -> None:
    hits = await search(query)
    for i, h in enumerate(hits, 1):
        print(f"[{i}] {h['source']} › {h['heading']}  score={h['score']}")
        print("   ", h["text"][:120].replace("\n", " "))
    print("\n--- 组装后的上下文长度:", len(format_context(hits)), "字符")


if __name__ == "__main__":
    import sys
    asyncio.run(demo(" ".join(sys.argv[1:]) or "第5周讲的四大失败模式是什么"))
```

```powershell
uv run python -m server.rag.retrieve "Checkpointer 和 thread 是什么关系"
```

预期：top 命中应包含 `08-第8周-持久化记忆与人工介入.md › Checkpointer：图的存档机制`。**如果命中的是别的文件，先调分块/查询措辞，别急着改生成 prompt**——这就是「检索与生成隔离」。

### 步骤 5：把检索做成 MCP Server（复用第 9 周）

`server/mcp_servers/notes_rag_server.py`——注意沿用第 9 周的 **2026-07-28 版无状态规范**、FastMCP、stdio、工具返回字符串：

```python
"""server/mcp_servers/notes_rag_server.py —— RAG 版笔记 MCP Server。
调试: npx @modelcontextprotocol/inspector uv run server/mcp_servers/notes_rag_server.py
"""
import json

from mcp.server.fastmcp import FastMCP

from server.rag.retrieve import format_context, search

mcp = FastMCP("course-notes-rag")


@mcp.tool()
async def search_notes(query: str, top_k: int = 4) -> str:
    """语义检索 12 周 Agent 课程笔记，返回带来源和相似度分数的命中段落。
    当用户询问课程内容、概念解释、某周讲了什么、代码怎么写时使用。
    不要用于实时天气、新闻、日程等非笔记内容。
    """
    hits = await search(query, min(max(top_k, 1), 8))
    return json.dumps({
        "query": query,
        "hits": [{"source": h["source"], "heading": h["heading"],
                  "score": h["score"], "preview": h["text"][:300]} for h in hits],
    }, ensure_ascii=False)


@mcp.tool()
async def get_notes_context(query: str, top_k: int = 4) -> str:
    """检索并组装好可直接放进上下文的资料块（带 [1][2] 引用锚点）。
    在需要基于笔记回答问题时使用；先用 search_notes 确认命中也可。
    """
    hits = await search(query, min(max(top_k, 1), 8))
    return format_context(hits)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

> **规范避坑**（第 9 周原话）：2026-07-28 版核心无状态、取消了 `initialize` 握手。看到旧教程里的 `session_id` / 握手代码直接忽略。判断新旧：搜「initialize handshake」。

**两个工具的分工**是第 5 周 schema 四原则的实操：`search_notes` 描述里明确写了「不要用于实时天气/新闻/日程」，防止语义误触发；`get_notes_context` 说明「在需要基于笔记回答时使用」。描述含糊 = 模型传错参数，一期实验已经证明过。

接入 Agent（沿用第 9 周 `MultiServerMCPClient` 的配置，只换 command）：

```python
client = MultiServerMCPClient({
    "notes-rag": {
        "command": "uv",
        "args": ["run", "server/mcp_servers/notes_rag_server.py"],
        "transport": "stdio",
    },
    "agenda": {                      # 一期原有的日程 MCP，保持不动
        "command": "uv",
        "args": ["run", "server/mcp_servers/agenda_server.py"],
        "transport": "stdio",
    },
})
tools = client.get_tools()
```

**验收点**：Agent 代码里看不到任何向量库、嵌入、分块逻辑——和第 9 周「工具从进程内函数变成标准服务」是同一个结论，只是这次换成了语义检索。

### 步骤 6：无嵌入模型 / 无 chromadb 的备选

如果平台没有 `/embeddings`，或 chromadb 装不上，用纯 numpy 的关键词 + 字符 n-gram 版（效果差些，但链路完整、零外部依赖）：

`server/rag/simple_index.py`：

```python
"""server/rag/simple_index.py —— 零依赖备选：字符 bigram TF-IDF 余弦相似度。"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

from server.rag.ingest import split_markdown, NOTES_DIR, INCLUDE

INDEX = Path("eval/rag_index/simple.json")


def gram(text: str) -> set[str]:
    t = re.sub(r"\s+", "", text.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def build() -> None:
    chunks = [c for p in sorted(NOTES_DIR.glob("*.md"))
              if INCLUDE.match(p.name) for c in split_markdown(p)]
    grams = [gram(c["text"]) for c in chunks]
    vocab = {g for s in grams for g in s}
    index = {g: i for i, g in enumerate(sorted(vocab))}
    mat = np.zeros((len(chunks), len(index)), dtype=np.float32)
    for r, s in enumerate(grams):
        for g in s:
            mat[r, index[g]] = 1.0 / math.sqrt(len(s) or 1)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps({
        "chunks": chunks, "vocab": index, "mat": mat.tolist(),
    }, ensure_ascii=False), encoding="utf-8")
    print(f"built {len(chunks)} chunks, vocab={len(index)}")


async def search(query: str, top_k: int = 4) -> list[dict]:
    """与 retrieve.search 保持同名同签名（async），便于整体替换。"""
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    mat = np.array(data["mat"], dtype=np.float32)
    q = np.zeros(mat.shape[1], dtype=np.float32)
    gs = gram(query)
    for g in gs & set(data["vocab"]):
        q[data["vocab"][g]] = 1.0 / math.sqrt(len(gs) or 1)
    sims = mat @ q
    top = np.argsort(-sims)[:top_k]
    return [{"text": data["chunks"][i]["text"],
             "source": data["chunks"][i]["metadata"]["source"],
             "heading": data["chunks"][i]["metadata"]["heading"],
             "score": float(sims[i])} for i in top]


if __name__ == "__main__":
    build()
```

用它时把 `retrieve.py` 里的 `search()` 函数整体替换为 `from server.rag.simple_index import search`（同名 `async` 接口，`await search(...)` 的调用处不用改），`format_context()` 保持不变。**生产别用这个**，它只是保证你在任何环境下都能把链路跑通。

### 步骤 7：评估 —— 检索与生成分开测

`eval/rag_cases.jsonl`（10 条，从一期教程里自己出题）：

```json
{"q":"第5周讲的四大失败模式是什么","expect_sources":["05-第5周-Function-Calling与ReAct.md"],"expect_keywords":["死循环","上下文爆炸","早停","过度思考"]}
{"q":"Checkpointer 和 thread 的关系","expect_sources":["08-第8周-持久化记忆与人工介入.md"],"expect_keywords":["thread","快照"]}
{"q":"SSE 事件协议有哪几种 type","expect_sources":["10-第10周-项目需求与架构.md"],"expect_keywords":["delta","tool_call","interrupt","done","error"]}
{"q":"interrupt 之后怎么恢复","expect_sources":["08-第8周-持久化记忆与人工介入.md"],"expect_keywords":["Command","resume"]}
{"q":"MCP 有哪三大原语","expect_sources":["09-第9周-MCP协议.md"],"expect_keywords":["Tools","Resources","Prompts"]}
{"q":"为什么模型不执行函数","expect_sources":["05-第5周-Function-Calling与ReAct.md"],"expect_keywords":["JSON","Schema"]}
{"q":"工具 schema 设计四原则","expect_sources":["05-第5周-Function-Calling与ReAct.md"],"expect_keywords":["描述","枚举"]}
{"q":"第12周评估有哪些指标","expect_sources":["12-第12周-完善与作品集化.md"],"expect_keywords":["完成率","轮次","P50","P95"]}
{"q":"@Streaming 不加会怎样","expect_sources":["11-第11周-MVP打通.md"],"expect_keywords":["缓冲","流式"]}
{"q":"为什么选 SSE 不选 WebSocket","expect_sources":["10-第10周-项目需求与架构.md"],"expect_keywords":["单向"]}
```

`eval/rag_eval.py`：

```python
"""eval/rag_eval.py —— 只测检索，不调生成模型，快且便宜。
运行: uv run python -m eval.rag_eval
"""
import asyncio
import json
from pathlib import Path

from server.rag.retrieve import search, format_context
from server.base import call_model

CASES = Path("eval/rag_cases.jsonl")


async def main() -> None:
    rows = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        hits = await search(c["q"], top_k=4)
        sources = [h["source"] for h in hits]
        hit = any(any(e in s for s in sources) for e in c["expect_sources"])
        ctx_len = len(format_context(hits))
        kw = sum(1 for k in c["expect_keywords"]
                 if any(k in h["text"] for h in hits))
        rows.append({"q": c["q"], "recall@4": hit, "kw": kw,
                     "ctx": ctx_len, "top": sources[0]})
        print(f"{'✓' if hit else '✗'} {c['q'][:28]:<30} "
              f"kw={kw}/{len(c['expect_keywords'])} ctx={ctx_len} top={sources[0][:16]}")

    r4 = sum(r["recall@4"] for r in rows) / len(rows)
    print(f"\nRecall@4 = {r4:.2f}  平均上下文 = "
          f"{sum(r['ctx'] for r in rows)/len(rows):.0f} 字符")
    if r4 < 0.8:
        print("检索不达标 → 先调 chunk 大小 / top_k / 查询改写，不要急着改生成 prompt")
        raise SystemExit(1)
    print("检索达标 ✓ 现在才进入生成质量评估")


if __name__ == "__main__":
    asyncio.run(main())
```

**生成质量**再单独测：把 RAG 场景加进 `eval/tasks.json`，走 P0-02 的门禁：

```json
{"id":16,"scene":"notes","input":"第5周讲的四大失败模式分别是什么，各自怎么防","expect":"列出四种并给出对策，带引用","type":"正常","graders":{"structure":{"expect_tools":["get_notes_context"],"max_turns":4},"rubric":{"criteria":"四种失败模式齐全，每种给出对策，且回答中出现 [1] 这类引用锚点；不得编造教程里没有的第五种"}}}
```

跑全量：

```powershell
uv run python -m eval.rag_eval        # 先测检索
uv run python -m eval.run_eval        # 再测 16 条全链路门禁
```

### 步骤 8：更新作品集

- `docs/` 加一张 RAG 数据流图（离线 ingest / 在线 retrieve 两条线）
- README 增加「RAG」章节：语料规模（13 文件 / 2xx chunks）、embedding 模型与维度、Recall@4、平均上下文长度、为什么走 MCP
- 演示：问「第 6 周手写的三大护栏是什么」，App 里显示引用了 `06-第6周…` ——**带引用的回答比不带引用的可信得多**，这是很好的演示素材

---

## 4. 常见报错与修复

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| `/embeddings` 404 或模型名报错 | 平台不支持 / 名字不对 | 先跑 `probe_embed.py`；或走步骤 6 的 numpy 备选 |
| 换了 embedding 模型后结果全乱 | 向量维度/语义空间变了，旧索引失效 | **删除 `eval/rag_index/` 重建索引**；把模型名写进索引 metadata 便于校验 |
| 检索命中代码块半截 | 按固定字数硬切 | 按 `## / ###` 结构切；超长才按段落二次切并带 overlap |
| 命中全是 README 或不相关文件 | README 太短、查询太泛 | 给 chunk 加 `week` metadata；查询改写（「第5周 四大失败模式」比「失败模式」准） |
| 回答不引用、开始编造 | 生成侧没约束 | `format_context` 的 header 明确要求 `[1][2]`；rubric grader 断言引用锚点 |
| 上下文又爆了 | top_k 太大 / chunk 太长 | `RAG_MAX_CONTEXT` 硬预算（默认 3500 字符），与 P0-03 的 token 上限叠加 |
| MCP Inspector 看不到工具 | 用了旧版握手代码 | 按 2026-07-28 无状态规范，用 FastMCP + stdio |
| `asyncio.run` 在 MCP 工具里报「事件循环已运行」 | Host 已在异步上下文 | 改成 `await search(...)` 并把工具函数声明为 `async def`（FastMCP 支持） |
| 加新场景后旧 15 条退步 | 工具变多导致选择错误率上升 | 第 5 周讲过 >10 个工具时错误率上升；用 P0-02 门禁盯住，必要时按场景分组挂载工具 |

---

## 5. 验收自测

- [ ] `probe_embed.py` 确认嵌入接口可用并记下维度
- [ ] `ingest` 建索引完成，人工抽查 2 个 chunk 无代码块断裂
- [ ] `retrieve` 对 3 个自测问题命中正确文件，输出带来源与分数
- [ ] `Recall@4 ≥ 0.8`，且检索不达标时先调检索而非 prompt
- [ ] MCP Inspector 能看到 `search_notes` / `get_notes_context` 并成功调用
- [ ] Agent 通过 MCP 完成「检索 → 带引用回答」，代码里无向量库痕迹
- [ ] 全量 16 条 eval 门禁通过，原 15 条无退步
- [ ] README 的 RAG 章节有语料规模 / 模型 / Recall / 上下文长度数据
- [ ] 代码提交 git，`NEXT.md` 记下 Recall@4 与平均上下文长度

**自测题**：

1. 为什么中文 Markdown 教程按 `## / ###` 结构切块，比按固定字数切更好？
2. 检索命中率只有 0.6，最不该先做的是什么？为什么？
3. 为什么要把 RAG 做成 MCP Server 而不是在 Agent 里直接调 `search()`？
4. 换 embedding 模型为什么必须重建索引？
5. 引用锚点 `[1][2]` 除了让回答可信，在工程上还解决了什么（提示：P0-01 trace / 失败归因）？

---

## 6. 衔接

- 若你选的是 **P1 单方向做深**：本模块完成即可，跳到 `P1-03-框架对比式学习与文章.md` 把成果写成文章，或按兴趣进入 P2。
- 若你后面想做 **P1-02 分层多 Agent**：这里的 `get_notes_context` 正好可以变成「笔记专员」的专属工具，是天然的 specialist 划分依据。
- 无论走哪条，都继续用同一套 trace + eval 门禁验证，不要回到「读完就算学会」。
