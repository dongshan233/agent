import asyncio

### 1.asyncio
async def fetch(name:str,delay:float) -> str:
    await asyncio.sleep(1000)    #非阻塞等待
    return f"{name}完成"

async def main() ->None:
    #串行，delay =delay1+delay2
    r1 = await fetch("A",1.0)
    r2 = await fetch("B",1.0)
    #并发 dealy = max(delay1,delay2,delay3)
    results = await asyncio.gather(
        fetch("A",1.0),
        fetch("B",1.0),
        fetch("C",1.0)
    )
asyncio.run(main())

##3.11推荐TaskGroup（结构化并发，一个失败全部取消）：
async def main() ->None:
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(fetch("A",1.0))
        t2 = tg.create_task(fetch("B",1.0))
    print(t1.result(),t2.result())



### 2.httpx:Python世界的okhttp




