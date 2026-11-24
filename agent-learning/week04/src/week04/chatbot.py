#命令行多轮聊天机器人
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
BASE = os.environ['LLM_BASE_URL']
KEY = os.environ['LLM_API_KEY']
MODEL = os.environ['LLM_MODEL']

SYSTEM_PROMPT = "你是一个简洁友好的中文助手，回答控制在200以内"

def chat_stream(history:list[dict]) -> str:
    payload = {
        "model":MODEL,
        "messages":history,
        "temperature":0.7,
        "stream":True,
    }
    headers = {"Authorization":f"Bearer {KEY}"}
    full = ""
    url = f"{BASE}/chat/completions"
    with httpx.stream("POST",url,headers=headers,json=payload,timeout =120) as resp:
        if resp.status_code != 200:
                resp.read()
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                break
            choices =  json.loads(data)["choices"] or []
            if not choices:
                continue
            delta = choices[0].get("delta",{})
            # := 海象运算符,
            #piece := ... —— 把取到的值赋给变量 piece。
            # := 是"赋值表达式"，和普通赋值语句的区别是它本身有返回值，可以嵌在 if、while 等表达式内部。
            #所以能直接加if判断
            if piece := delta.get("content",""):
                full+=piece
                print(piece,end="",flush=True)#end="" 不换行，让增量首尾相接形成打字机效果；flush=True 立刻刷出缓冲区，不等攒批。
    print()
    return full

def main()->None:
    history:list[dict] = [{"role":"system","content":SYSTEM_PROMPT}]
    print("输入消息对话；/clear 清空历史对话；/exit 退出")
    while True:
        user = input("\n你> ").strip()
        if not user:
            continue
        if user == "/exit":
            break
        if user == "/clear":
            history=[{"role":"system","content":SYSTEM_PROMPT}]
            print("历史已清空")
            continue
        history.append({"role":"user","content":user})
        try:
            reply = chat_stream(history)
            history.append({"role":"assistant","content":reply})
        except httpx.HTTPStatusError as e:
            print(f"\n[HTTP {e.response.status_code}] {e.response.text[:200]}")
if __name__ == "__main__":
    main()