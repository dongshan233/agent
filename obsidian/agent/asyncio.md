## 1. asyncio基础知识：

1.1 核心映射表

| Kotlin 协程            | Python asyncio                         | 说明                  |
| -------------------- | -------------------------------------- | ------------------- |
| `suspend fun`        | `async def`                            | 定义挂起函数              |
| 挂起点                  | `await`                                | 只有 async 函数内能 await |
| `runBlocking { }`    | `asyncio.run(main())`                  | 桥接同步世界 → 异步世界       |
| `coroutineScope { }` | `asyncio.TaskGroup` / `asyncio.gather` | 结构化并发               |
| `async/awaitAll`     | `asyncio.gather(t1, t2, ...)`          | 并发多个任务              |
| `Dispatchers.IO`     | `asyncio.to_thread(...)`               | 把阻塞操作丢到线程池          |
| `Job.cancel()`       | `task.cancel()`                        | 取消任务                |
| `Mutex`              | `asyncio.Lock`                         | 协程间互斥               |
```python
import asyncio

async def fetch(name: str, delay: float) -> str:      # ≈ suspend fun fetch(): String
    await asyncio.sleep(delay)                        # 非阻塞等待 ≈ delay()
    return f"{name} 完成"

async def main() -> None:
    # 串行：总耗时 = delay1 + delay2
    r1 = await fetch("A", 1.0)
    r2 = await fetch("B", 1.0)

    # 并发：总耗时 ≈ max(delay1, delay2)  ≈ Kotlin async/awaitAll
    results = await asyncio.gather(
        fetch("A", 1.0),
        fetch("B", 1.0),
        fetch("C", 1.0),
    )
    print(results)   # ['A 完成', 'B 完成', 'C 完成']，顺序与传入顺序一致

asyncio.run(main())   # ≈ runBlocking { main() }
```

3.11 推荐用 `TaskGroup`（结构化并发，一个失败全部取消）：
```python
async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(fetch("A", 1.0))
        t2 = tg.create_task(fetch("B", 1.0))
    print(t1.result(), t2.result())
```

## 2.httpx:Python世界的OkHttp

安装:`uv add httpx python-dotenv`。
```python
import httpx
#同步用法
with httpx.Client(timeout=10) as client:
	resp = client.get("https://httpbin.org/get",params={"q":"hi"})
	resp.raise_for_status() # ≈ 检查HTTP错误码，非2xx抛异常
	data = resp.json()      # Gson解析
	
#异步用法
async with httpx.AsyncClient(timeout=10) as client:
	resp = await client.post("https://httpbin.org/post",json={"key":"value"})
	print(resp.status_code,resp.json())
```