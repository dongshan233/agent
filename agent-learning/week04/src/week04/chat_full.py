import httpx,os,json
from dotenv import load_dotenv

load_dotenv()

def stream_chat(messages,*,temperature=0,max_tokens=500,show_reasoning=True):
    content_parts,reasoning_parts = [],[]
    finish_reason,usage = None,None
    in_reasoning = False

    with httpx.Client(timeout=httpx.Timeout(60,read=300)) as client:
        with client.stream(
            "POST",
            f"{os.environ['LLM_BASE_URL']}/chat/completions",
            headers={"Authorization":f"Bearer {os.environ['LLM_API_KEY']}"},
            json={
                "model":os.environ['LLM_MODEL'],
                "messages":messages,
                "stream":True,
                #让服务端在流末尾多发送一个usage统计包，个别网关不支持此参数，如报400删掉即可
                "stream_options":{"include_usage":True},
                "temperature":temperature,
                "max_tokens":max_tokens,
            }
        ) as resp:
            if resp.status_code != 200:
                resp.read()
                print("HTTP",resp.status_code)
                print(resp.text)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue   #跳过空行和心跳
                data = line[len("data:"):].strip()
                if data== "[DONE]":
                    break # 跳过结束符
                chunk = json.loads(data)

                #usage包：choice为空，统计在这里取
                if chunk.get("usage"):
                    usage=chunk["usage"]

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]

                if choice.get("finish_reason"):
                    finish_reason = choice["finish_reason"]

                delta = choice.get("delta") or {}

                #思考和回答各自单独判断，不用elif，兼容任意时序
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    if not in_reasoning:
                        if show_reasoning:
                            print("--思考中--")
                        in_reasoning=True
                    reasoning_parts.append(reasoning)
                    if show_reasoning:
                        print(reasoning,end="",flush=True)
                content = delta.get("content")
                if content:
                    if in_reasoning:
                        if show_reasoning:
                            print()
                            print("--回答--")
                        in_reasoning = False
                    content_parts.append(content)
                    print(content,end="",flush=True)
    print()#收尾换行
    return{
        "content":"".join(content_parts),
        "reasoning":"".join(reasoning_parts),
        "finish_reason":finish_reason,
        "usage":usage
    }

if __name__ == "__main__":
    question = "你给我翻译翻译，什么他妈的是他妈的惊喜"
    result = stream_chat([
        {"role":"system","content":"你是一个简洁的助手"},
        {"role":"user","content":question}
    ])
    print("finish reason:",result["finish_reason"])
    print("usage:",result["usage"])
    if result["finish_reason"] == "length":
        print("注意：输出被 max_tokens 截断，建议调大上限")
    if result["finish_reason"] == "length" and not result["content"]:
        print("注意：思考阶段就耗尽了max_tokens，正式回答一个字没有输出,推理模型需要更大上限")

    history = [
        {"role":"user","content":question},
        {"role":"assistant","content":result["content"]},
    ]