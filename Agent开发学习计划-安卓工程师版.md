# Agent 开发学习计划（安卓工程师定制版）

> 制定日期：2026-11-17
> 学员背景：安卓开发工程师，主力语言 Kotlin/Java，Python 了解阶段
> 总周期：12 周（约 3 个月）
> 时间预算：每周 8~10 小时（工作日每天约 1 小时 + 周末合计 3~4 小时）
> 学习方式：项目驱动，每周必须有可运行的代码产出

---

## 总览

| 阶段 | 周次 | 主题 | 关键产出 |
| --- | --- | --- | --- |
| 一 | 第 1~3 周 | Python 从了解到够用 | 3 个 Python 小项目 |
| 二 | 第 4~5 周 | LLM API 与底层机制 | 带工具调用的命令行聊天机器人 |
| 三 | 第 6 周 | 手写最小 Agent（无框架） | 约 150 行的 ReAct Agent |
| 四 | 第 7~9 周 | LangGraph + MCP | 图编排 Agent + 自写 MCP Server |
| 五 | 第 10~12 周 | 安卓 + Agent 实战项目 | 可演示的完整 App + 后端 Agent |

每周节奏建议：周一至周四每天 1 小时（学概念 + 写代码），周五休息或补进度，周末集中 3~4 小时完成本周练习项目并自测验收。

---

## 阶段一：Python 从了解到够用（第 1~3 周）

目标不是精通 Python，而是达到「能顺畅读写 Agent 生态代码」的水平。你有 Kotlin 功底，重点是语法映射和生态工具，不要从零刷入门视频。

### 第 1 周：环境 + 语法映射

**准备（周末前完成）**
1. 安装 Python 3.11+，推荐用 uv 管理环境和依赖（对应安卓世界的 Gradle 角色）
2. 编辑器：VS Code + Python 插件，或 PyCharm Community
3. 建一个 git 仓库 `agent-learning`，之后所有练习代码都提交进去，按周建目录

**学习内容（对照 Kotlin 学，效率最高）**
- 变量与类型：动态类型 vs Kotlin 静态类型；`None` vs `null`
- 函数：默认参数、关键字参数、`*args/**kwargs`
- 控制流：`for ... in`、`enumerate`、没有花括号靠缩进
- 核心数据结构：`list` / `dict` / `tuple` / `set`，对应 Kotlin 的 List/Map/Pair/Set
- 列表推导式：`[x*2 for x in nums if x > 0]`，对应 `map/filter`
- 字符串：f-string 对应 Kotlin 字符串模板

**本周练习**：把你写过的一个 Kotlin 小工具（比如日志解析、文件重命名）用 Python 重写。

**验收标准**
- [ ] 不查教程写出一个命令行 TODO 工具：支持增/删/列，数据用 JSON 文件持久化
- [ ] 能解释 Python 的可变默认参数陷阱（`def f(x=[])` 为什么危险）

### 第 2 周：函数进阶 + OOP + 类型标注 + pydantic

**学习内容**
- 类与对象：`__init__`、`self`（对应 Kotlin 的 this）、`dataclass`（对应 data class）
- 模块与包：`import` 机制、`if __name__ == "__main__"`
- 类型标注：`typing` 模块、`Optional`、`TypedDict`——Agent 框架大量使用，必须熟
- 异常处理：`try/except/finally`，自定义异常
- **pydantic**：定义模型、字段校验、`model_validate` / `model_dump`。这是 Function Calling schema 和几乎所有 Agent 框架的地基，本周重点

**本周练习**：用 pydantic 定义一个「安卓设备信息」模型（型号、系统版本、内存、已安装应用列表），从 JSON 加载并校验，故意传错类型观察报错。

**验收标准**
- [ ] 能独立定义带嵌套模型、默认值、字段校验的 pydantic 类
- [ ] 能看懂并解释 `Annotated[list, add_messages]` 这类写法（第 7 周 LangGraph 会用到）

### 第 3 周：异步 + 网络请求 + 测试

**学习内容**
- asyncio：`async/await`、`asyncio.gather`。直接对照 Kotlin 协程理解：`suspend` ≈ `async def`，`await` ≈ 挂起点，`gather` ≈ `async/awaitAll`
- HTTP 客户端：`httpx`（支持异步），对应 Retrofit/OkHttp 的角色
- 环境变量与密钥管理：`python-dotenv`，API Key 放 `.env` 且不提交 git
- pytest 基础：写测试函数、断言、运行

**本周练习**：写一个异步脚本，并发请求 3 个公开 API（如天气、汇率、IP 归属地），汇总结果输出，对比串行和并发的耗时。

**验收标准**
- [ ] 能解释事件循环是什么、为什么不能在 async 函数里调阻塞 IO
- [ ] 并发脚本跑通，且给核心逻辑写了至少 2 个 pytest 用例

---

## 阶段二：LLM API 与底层机制（第 4~5 周）

这一阶段不碰任何 Agent 框架。目标是搞懂「模型到底怎么工作、工程上会坏在哪」。

### 第 4 周：LLM API 入门

**准备**
1. 注册一个模型平台并充值少量额度（国内推荐阿里云百炼/通义或 DeepSeek，海外可选 OpenAI/Anthropic，接口模式相通）
2. API Key 写入 `.env`

**学习内容**
- Chat Completions 接口：`messages` 数组结构（system / user / assistant 三种角色）
- 关键参数：temperature、max_tokens、流式输出（stream）
- token 概念：计费单位、上下文窗口限制
- 多轮对话本质：每轮把完整历史重新发给模型，模型本身无状态——这点和你熟悉的 HTTP 无状态是一回事

**本周练习**：写一个命令行聊天机器人，支持多轮对话 + 流式输出 + `/clear` 清空历史。

**验收标准**
- [ ] 能画出一次对话请求的完整 messages 结构
- [ ] 能解释「模型没有记忆，记忆是你拼进 messages 的」

### 第 5 周：Function Calling + ReAct + 上下文管理

**学习内容（本计划最核心的一周，宁可慢不可跳）**
- Function Calling 真相：模型不执行任何函数，它只按你给的 JSON schema 输出一段「我想调用什么工具、参数是什么」的 JSON；你的代码解析 → 执行真实函数 → 把结果作为 tool 消息塞回 → 模型继续生成
- 工具 schema 设计：描述要具体、参数类型和枚举写全、给示例。描述含糊 = 模型传错参数，这是工程问题不是玄学
- ReAct 循环：Thought → Action → Observation → 再 Thought
- 四大失败模式：死循环（反复重试）、上下文爆炸（轮次太多塞满窗口）、早停（没拿到关键信息就宣布完成）、过度思考（推理模型钻牛角尖，需设预算上限）
- 上下文管理：长窗口 ≠ 好用；无关内容越多准确率越低（context rot）；关键信息放头尾（lost in the middle 现象）；主动剪枝历史

**本周练习**：给第 4 周的聊天机器人接上 2 个工具——计算器（精确数学）+ 一个真实 API 工具（天气或搜索）。手动解析 tool_calls、手动回填结果。

**验收标准**
- [ ] 提问「苏州今天多少度，比 25 度高几度」能触发两次工具调用并给出正确答案
- [ ] 能口头讲清一次工具调用的完整消息流转（4 条消息各是什么角色）
- [ ] 故意把工具描述写模糊，观察并记录模型传错参数的现象

---

## 阶段三：手写最小 Agent（第 6 周）

**目标**：不用任何框架，约 150 行代码实现完整 Agent 循环。这一步搞透，后面学框架时你知道每个 API 在替你做什么。

**执行步骤**
1. 周一~周二：搭主循环——`while` 循环里调模型 → 判断返回是工具调用还是最终回答 → 执行工具回填 → 继续，直到给出答案或达到最大轮次
2. 周三：加护栏——最大迭代次数（如 10 轮）、工具执行 try/except、每轮打印日志（第几轮、调了什么工具、参数、结果）
3. 周四：加第 3 个工具（如读取本地文件），验证模型能自主规划多工具组合
4. 周末：测试与复盘——准备 5 个测试任务（含 1 个故意无解的），记录成功/失败情况；写 200 字复盘：哪里最容易坏

**验收标准**
- [ ] 完成「查 A 信息 → 用 A 做计算 → 汇总回答」的两步以上任务
- [ ] 无解任务不会死循环，达到轮次上限后优雅退出
- [ ] 日志能完整还原 Agent 每一步决策

---

## 阶段四：LangGraph + MCP（第 7~9 周）

### 第 7 周：LangGraph 基础

**学习资源**：LangChain Academy 官方免费入门课（Introduction to LangGraph）+ 官方文档 docs.langchain.com

**学习内容**
- StateGraph：State（TypedDict 定义共享状态）、Node（干活的函数）、Edge（流转关系）
- 条件边（conditional edges）：根据状态决定下一步——本质是状态机，对照安卓页面导航图理解
- `add_messages` 消息合并机制

**本周练习**：把第 6 周的手写 Agent 重构成 LangGraph 图：模型节点 + 工具节点 + 条件边。

**验收标准**
- [ ] 重构后功能与手写版一致
- [ ] 能画出自己 Agent 的图结构（节点、边、条件）
- [ ] 能说出框架替你做了哪些你上周手写的事

### 第 8 周：持久化 + 记忆 + 人工介入

**学习内容**
- Checkpointer：保存图状态，进程重启后对话可恢复（对照安卓的 onSaveInstanceState / 进程恢复）
- 短期记忆（会话内）vs 长期记忆（跨会话存储）
- human-in-the-loop：关键操作前中断等待用户确认（interrupt 机制）

**本周练习**：给 Agent 加「删除文件前必须人工确认」的中断点；杀掉进程重启后恢复对话。

**验收标准**
- [ ] 中断 → 确认 → 继续的完整链路跑通
- [ ] 重启后 Agent 记得之前的对话内容

### 第 9 周：MCP 协议

**背景**：MCP（Model Context Protocol）已是工具接入的事实标准，OpenAI、Google 等均已采纳。注意：2026 年 7 月发布了大改版规范（2026-07-28 版，转向无状态核心、取消初始化握手），学习时认准新版文档，旧教程里的会话握手内容已过时。

**学习资源**：modelcontextprotocol.io 官方文档（Getting Started → 搭建 MCP 服务器）

**学习内容**
- 架构：Host / Client / Server 三角色
- 核心原语：Tools / Resources / Prompts
- 传输方式：stdio（本地）与 Streamable HTTP（远程）
- 用官方 Python SDK 写 Server

**本周练习**：写一个自己的 MCP Server，暴露 2~3 个工具（如「查询我的笔记」「列出某目录文件」），用官方 Inspector 工具调试，再接入第 8 周的 LangGraph Agent。

**验收标准**
- [ ] Inspector 里能看到并成功调用你的工具
- [ ] LangGraph Agent 能通过 MCP 调用你写的工具完成任务

---

## 阶段五：安卓 + Agent 实战项目（第 10~12 周）

**项目建议**：「手机智能助理」——安卓 App（你的主场）+ Python 后端 Agent。用户语音/文字提需求，Agent 规划并调用工具完成，结果回显 App。这是你区别于其他 Agent 学习者的差异化作品。

### 第 10 周：需求与架构
1. 定 3 个核心场景（示例：查天气并给穿衣建议、搜索资讯并摘要、查询手机日程并总结）——宁少勿多
2. 架构：App（Kotlin， Retrofit/OkHttp 对接）↔ FastAPI 后端 ↔ LangGraph Agent ↔ 工具/MCP
3. 定义前后端接口（含流式响应方案：SSE）
4. 画出架构图和数据流图

**验收**：架构评审自查——每个组件职责单一、接口定义完整、有错误路径设计。

### 第 11 周：MVP 打通
1. 后端：FastAPI 包一层 Agent，暴露对话接口（支持 SSE 流式）
2. App：一个对话界面（复用你熟悉的 RecyclerView + 协程即可），接通后端
3. 打通 1 个核心场景端到端

**验收**：真机上完成「输入需求 → Agent 调工具 → 流式返回答案」全链路。

### 第 12 周：完善与作品集化
1. 补齐另外 2 个场景
2. 加评估：准备 10 个测试任务，记录任务完成率、平均轮次、失败原因分类
3. 加成本意识：记录每次请求 token 消耗
4. 写 README：架构图、演示 GIF、评估数据、踩坑记录
5. 复盘：对照第 6 周手写版，总结框架/协议各自解决了什么问题

**验收**：仓库可以直接作为求职/转岗作品集展示；能向别人 10 分钟讲清整个系统。

---

## 资源清单

- 路线图查漏补缺：roadmap.sh/ai-agents
- LangGraph 官方课：LangChain Academy（academy.langchain.com，免费）
- LangChain/LangGraph 文档：docs.langchain.com
- MCP 官方文档：modelcontextprotocol.io（认准 2026-07-28 版规范）
- 模型平台：阿里云百炼 / DeepSeek 开放平台（国内），OpenAI / Anthropic（海外）
- Python 异步：官方 asyncio 文档 + 对照 Kotlin 协程迁移理解

## 三条纪律

1. **每周必须有可运行代码提交 git**，看视频不算进度
2. **不囤教程**：每个阶段只用列出的主资源，卡住先读官方文档再搜索
3. **验收标准过了才进下一周**；某周没达标就顺延，宁可 14 周走完也不要带着窟窿前进

## 风险预警

- 第 5 周是全程最陡的坡（概念密度最大），预留缓冲，必要时拆成两周
- 第 9 周注意 MCP 新旧规范差异，旧博客的握手/会话代码不要照抄
- 阶段五切忌功能膨胀，3 个场景做深比 10 个场景做浅有价值
