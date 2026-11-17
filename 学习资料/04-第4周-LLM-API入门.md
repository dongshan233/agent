# 第 4 周：LLM API 入门

> 阶段二 · 第 4 周。本周不碰任何 Agent 框架，用裸 HTTP 搞懂模型 API 的工作方式。

## 学习目标

1. 亲手拼出一次 Chat Completions 请求，理解 `messages` 三种角色
2. 掌握 temperature / max_tokens / stream 参数的行为差异
3. 建立 token 与上下文窗口的直觉
4. 理解「多轮对话 = 客户端拼历史」，模型本身无状态
5. 产出：多轮对话 + 流式输出 + `/clear` 的命令行聊天机器人

## 1. 准备

1. 注册模型平台并充值少量额度：
   - 国内：阿里云百炼（通义）/ DeepSeek 开放平台
   - 海外：OpenAI / Anthropic
2. 各家接口都是 **OpenAI 兼容模式**，差别只在 `base_url` 和模型名。本资料以 OpenAI 兼容接口为准。
3. `.env`：

```powershell
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # 百炼示例
LLM_MODEL=qwen-plus
```

4. 安装：`uv add httpx python-dotenv`（继续用裸 httpx，不装 SDK——先把协议看透）。

## 2. Chat Completions：一次请求的解剖

```python
import httpx, os
from dotenv import load_dotenv

load_dotenv()

resp = httpx.post(
    f"{os.environ['LLM_BASE_URL']}/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
    json={
        "model": os.environ["LLM_MODEL"],
        "messages": [
            {"role": "system", "content": "你是一个简洁的助手。"},
            {"role": "user", "content": "用一句话解释什么是 token"},
        ],
        "temperature": 0.7,
        "max_tokens": 500,
    },
    timeout=60,
)
resp.raise_for_status()
print(resp.json()["choices"][0]["message"]["content"])
```

### 2.1 messages 三种角色（对照网络协议理解）

| role | 含义 | 类比 |
| --- | --- | --- |
| `system` | 长期指令：人设、规则、约束 | 请求头里的全局配置 |
| `user` | 用户输入 | 请求体 |
| `assistant` | 模型历史回复 | **你必须手动回填**的响应历史 |

第 5 周会加入第 4 种角色 `tool`（工具结果），先记住这三种。

### 2.2 响应结构

```json
{
  "choices": [{
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 25, "completion_tokens": 60, "total_tokens": 85}
}
```

- `finish_reason`：`stop`（正常结束）/ `length`（被 max_tokens 截断）/ `tool_calls`（想调工具，第 5 周见）
- `usage`：本次消耗的 token，第 12 周成本统计直接用它

## 3. 关键参数

| 参数 | 作用 | 工程建议 |
| --- | --- | --- |
| `temperature` | 随机性 0~2 | 抽取/分类/工具调用用 0~0.3；创意写作用 0.7+ |
| `max_tokens` | 本次生成的上限 | 设上限防跑飞；太小会 `finish_reason=length` 截断 |
| `stream` | SSE 流式返回 | 交互界面必开，感知延迟大幅下降 |
| `top_p` | 核采样 | 与 temperature 二选一调，不同时调 |

实验（10 分钟）：同一段 prompt 分别用 `temperature=0` 和 `1.5` 各跑 3 次，观察输出稳定性差异。

## 4. token 与上下文窗口

- **token**：模型的最小文本单位。英文约 1 token ≈ 0.75 词；中文约 1 字 ≈ 1~2 token。计费按 input + output token 算，**输入通常更便宜，但长对话里输入占大头**。
- **上下文窗口**：一次请求能塞进的总 token 上限（messages 全部内容 + 生成）。超出直接报错，不是自动截断。
- 上下文是**硬预算**：历史对话越长，每轮成本越高、响应越慢。这是第 5 周上下文管理的伏笔。

直觉练习：把一句长中文发给模型拿 `usage.prompt_tokens`，算出「每字约几 token」，建立换算手感。

## 5. 多轮对话的真相：模型无状态

这是本周最重要的心智模型，和 HTTP 无状态完全同构：

> **模型不保存任何对话。每一轮，你把完整历史（system + 历次 user/assistant）重新发一遍，模型根据这份「快照」生成下一个回复。**

```
第 1 轮发送: [system, user1]                → 收到 assistant1
第 2 轮发送: [system, user1, assistant1, user2]   → 收到 assistant2
第 3 轮发送: [system, user1, assistant1, user2, assistant2, user3] → ...
```

服务端看起来「记得你」，其实是**你的客户端维护着全部历史**。由此推论：

- 「忘记上下文」= 你的历史被清了或截了（责任在客户端）
- 「越聊越贵越慢」= 历史线性增长（需要主动管理）
- 「改第一句话的语气会影响后面」= 模型看到的是全量重放

对照安卓：≈ 你自己持有 session 缓存，每次请求全量上传；服务端无 cookie 无 session。

## 6. 流式输出（stream）

`stream=true` 时响应是 SSE（Server-Sent Events）流，服务端把回复切成小块持续推送：

```
data: {"choices":[{"delta":{"content":"你"}}]}
data: {"choices":[{"delta":{"content":"好"}}]}
data: [DONE]
```

每块的 `delta.content` 是增量文本，要**自己拼接**。对照安卓：≈ OkHttp 的 SSE source，也 ≈ 后端推 Flow，前端逐帧渲染。

```python
with httpx.stream(
    "POST", url, headers=headers, json={**payload, "stream": True}, timeout=120
) as resp:
    resp.raise_for_status()
    full = ""
    for line in resp.iter_lines():
        if not line.startswith("data: "):
            continue
        data = line.removeprefix("data: ")
        if data == "[DONE]":
            break
        delta = json.loads(data)["choices"][0].get("delta", {})
        piece = delta.get("content", "")
        full += piece
        print(piece, end="", flush=True)   # 逐字打印
```

## 7. 本周项目实战：命令行聊天机器人

需求：多轮对话 + 流式输出 + `/clear` 清空历史 + `/exit` 退出。

`week04/chatbot.py`：

```python
"""命令行聊天机器人：多轮 + 流式 + /clear。运行: uv run python chatbot.py"""
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
BASE = os.environ["LLM_BASE_URL"]
KEY = os.environ["LLM_API_KEY"]
MODEL = os.environ["LLM_MODEL"]

SYSTEM_PROMPT = "你是一个简洁友好的中文助手，回答控制在 200 字内。"


def chat_stream(history: list[dict]) -> str:
    """请求一次补全，流式打印并返回完整回复。"""
    payload = {
        "model": MODEL,
        "messages": history,
        "temperature": 0.7,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {KEY}"}
    full = ""
    url = f"{BASE}/chat/completions"
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                break
            delta = json.loads(data)["choices"][0].get("delta", {})
            if piece := delta.get("content", ""):
                full += piece
                print(piece, end="", flush=True)
    print()
    return full


def main() -> None:
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("输入消息对话；/clear 清空历史；/exit 退出")
    while True:
        user = input("\n你> ").strip()
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/clear":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("(历史已清空)")
            continue
        history.append({"role": "user", "content": user})
        try:
            reply = chat_stream(history)
            history.append({"role": "assistant", "content": reply})
        except httpx.HTTPStatusError as e:
            print(f"\n[HTTP {e.response.status_code}] {e.response.text[:200]}")


if __name__ == "__main__":
    main()
```

扩展任务：
1. 加 `/history` 命令：打印当前 `messages` 数组结构（为验收第 1 条服务）
2. 加 `/dump` 命令：把历史存成 JSON 文件，重启后可加载恢复
3. 记录每轮 `usage`（流式模式下很多平台在最后一个 chunk 的 `usage` 字段里给），打印累计 token

## 8. 验收自测

- [ ] 能画出一次对话请求的完整 `messages` 结构（在纸上画出第 3 轮的数组内容）
- [ ] 能解释「模型没有记忆，记忆是你拼进 messages 的」
- [ ] `/clear` 后机器人真的失忆了
- [ ] 流式输出逐字显示正常
- [ ] 代码提交 git

自测题：
1. `system` 消息和第一条 `user` 消息的区别？
2. `finish_reason=length` 说明发生了什么？用户视角会看到什么？
3. 为什么第 2 轮请求里必须带上第 1 轮的 assistant 回复？不带会怎样？

## 9. 衔接第 5 周

你的机器人现在「只会聊天」。第 5 周给它装上**手**——Function Calling：让模型请求调用你的计算器和天气 API。这是整个计划最陡的一周，概念密度最大，宁可慢不可跳。第 5 周见。
