#并发请求多个API并汇总uv run python concurrent_Fetch.py
import asyncio
import time

import httpx

APIS =[
    ("汇率","https://open.er-api.com/v6/latest/USD"),
    ("IP归属","http://ip-api.com/json/"),
    ("随机用户","https://randomuser.me/api/"),
]

async def fetch(client:httpx.AsyncClient,name:str,url:str) -> dict:
    for attemp in range(3):
        resp = await client.get(url,timeout=10)
        if resp.status_code ==429:
            wait = float(resp.headers.get("Retry-After",2 ** attemp)) #Retry-After 响应头：429 响应常带这个头，服务器会告诉你等多少秒，优先听它的；没有就用指数退避（1s → 2s → 4s）。
            print(f"[{name} 被限流]，{wait}s后重试")
            await asyncio.sleep(wait)
            continue
        resp.raise_for_status()
        return {"name":name,"data":resp.json()}
    return {"name":name,"data":None}

def summarize(results:list[dict]) -> str:
    lines=[]
    for r in results:
        body = r["data"]
        if "rates" in body:
            lines.append(f"{r['name']}:1 USD = {body['rates'].get('CNY')} CNY")
        elif "ip" in body:
            lines.append(f"{r['name']}:{body.get('city')} ({body.get('ip')})")
        else:
            lines.append(f"{r['name']}:OK")
    return "\n".join(lines)

async def run(parallel:bool) -> float:
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        if parallel:
            results = await asyncio.gather(*(fetch(client,n,u) for n,u in APIS))
        else:
            results = [await fetch(client,n,u) for n,u in APIS]
    print(summarize(results))
    return time.perf_counter()-start

async def main() ->None:
    t1 = await run(parallel=False)
    t2 = await run(parallel=True)
    print(F"\n串行 {t1:.2f}s vs 并发 {t2:.2f}s")
    #assert :"断言"：向程序声明一个必须成立的事实——t2（并行耗时）必须小于 t1（串行耗时）；
    # 如果不成立，程序立刻抛 AssertionError，并附上你写的那句提示"并发应该更快"。
    assert t2 <t1,"并发应该更快"

if __name__ == "__main__":
    asyncio.run(main())