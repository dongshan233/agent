"""带工具的聊天机器人"""

import json
import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
BASE, KEY, MODEL = (os.environ[k] for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"))


# 工具实现
def calculator(expression: str) -> str:
    """安全求值：只允许数字和四则运算符"""
    allowed = set("0123456789+-*/(). ")  # 字符集合
    # set(expression) 把输入字符串拆成单个字符的集合，比如 "1+2" → {'1', '+', '2'}
    # <= 用在集合上是子集判断（不是数值比较）：检查输入的每个字符是否都在白名单里。
    if not set(expression) <= allowed:
        return "错误：表达式包含非法字符"
    try:
        return str(
            eval(expression)
        )  # eval() 把字符串当 Python 代码执行，"1+2*3" 会算出 7
    except Exception as e:
        return f"计算失败：{e}"


async def get_weather(city: str, client: httpx.AsyncClient) -> str:
    geo = await client.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "language": "zh"},
        timeout=10,
    )
    geo.raise_for_status()
    hits = geo.json().get("results")
    if not hits:
        return f"错误：找不到城市{city}"
    loc = hits[0]
    wx = await client.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current_weather": True,
        },
        timeout=10,
    )
    wx.raise_for_status()
    cur = wx.json()["current_weather"]
    return json.dumps(
        {
            "city": loc["name"],
            "temp_c": cur["temperature"],
            "wind_kmh": cur["windspeed"],
        },
        ensure_ascii=False,
    )


# ---工具 schema------
class CalcArgs(BaseModel):
    """执行精确的数学四则运算。需要数学计算（加减乘除）时使用，不要心算"""

    expression: str = Field(description="数学表达式，如'18+7'或'(3+4)*2'")


class WeatherArgs(BaseModel):
    """查询指定城市当前气温和风速。用户询问天气时使用。"""

    city: str = Field(description="中文城市名，如'苏州'")


TOOL_FUNCS = {"calculator": calculator, "get_weather": get_weather}


def build_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": CalcArgs.__doc__,
                "parameters": CalcArgs.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": WeatherArgs.__doc__,
                "parameters": WeatherArgs.model_json_schema(),
            },
        },
    ]


# -----------主循环----------------
async def run_turn(history: list[dict], tools: list[dict],client) -> None:
    url, headers = f"{BASE}/chat/completions", {"Authorization": f"Bearer {KEY}"}
    payload = {
        "model": MODEL,
        "messages": history,
        "tools": tools,
        "tool_choice": "auto",
    }

    resp = await client.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code!=200:
        print(resp.status_code,resp.text)
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]

    if not msg.get("tool_calls"):
        print(f"\n助手> {msg['content']}")
        history.append({"role": "assistant", "content": msg["content"]})
        return
    history.append(
        {
            "role": "assistant",
            "content": msg.get("content"),
            "tool_calls": msg["tool_calls"],
        }
    )

    for tc in msg["tool_calls"]:
        name = tc["function"]["name"]
        args = json.loads(tc["function"]["arguments"])
        print(f" [调用工具] {name}({args})")
        if name == "get_weather":
            result = await get_weather(client=client,**args)
        else:
            result = TOOL_FUNCS[name](**args)
        print(f" [工具结果] {result}")
        history.append(
            {"role": "tool", "tool_call_id": tc["id"], "content": str(result)}
        )

    await run_turn(history, tools,client)


async def main() -> None:
    tools = build_tools()
    history = [
        {
            "role": "system",
            "content": "你是能使用工具的助手。数学必须用 calculator 工具。",
        }
    ]
    async with httpx.AsyncClient(timeout=60) as client:
        while True:
            user = input("\n你> ").strip()
            if user in ("/exit", ""):
                break
            history.append({"role": "user", "content": user})
            await run_turn(history, tools,client)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
