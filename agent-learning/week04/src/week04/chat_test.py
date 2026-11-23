import httpx,os,json
from dotenv import load_dotenv
load_dotenv()
#接口方式
# resp = httpx.post(
#     f"{os.environ['LLM_BASE_URL']}/chat/completions",
#     headers={"Authorization":f"Bearer {os.environ['LLM_API_KEY']}"},
#     json={
#         "model":os.environ['LLM_MODEL'],
#         "messages":[
#             # role:
#                 # system:长期指令：人设、规则、约束
#                 # user:  用户输入
#                 # assistant: 模型历史回复
#             {"role":"system","content":"你是一个简洁的助手。"},
#             {"role":"user","content":"用一句话解释什么是 token"},
#         ],
#         "stream":False,#是否以流式输出方式回复
#         "temperature":0,#随机性 0~2,工程建议:抽取/分类/工具调用用 0~0.3；创意写作用 0.7+
#         "max_tokens":500,#本次生成的上限,工程建议:设上限防跑飞；太小会 `finish_reason=length` 截断
#     },
#     timeout=60,
# )
# resp.raise_for_status()
# print(resp.json())


#流式返回
with httpx.Client(timeout=60) as client:
    with client.stream(
        "POST",
        f"{os.environ['LLM_BASE_URL']}/chat/completions",
        headers={"Authorization":f"Bearer {os.environ['LLM_API_KEY']}"},
        json={
            "model":os.environ["LLM_MODEL"],
            "messages":[
                {"role":"system","content":"你是一个简洁的助手"},
                {"role":"user","content":"用一句话解释什么是token"},
            ],
            "stream":True,
            "temperature":0,
            "stream_options":{"include_usage":True},
            "max_tokens":500,
        }
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():#按行读取
            print("\n[DEBUG]",line)
            if not line or not line.startswith("data:"):
                continue     #跳过空行和心跳
            data = line[len("data:"):].strip()
            if data =="[DONE]":   #流结束标记
                break
            chunk = json.loads(data)
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta =chunk["choices"][0]["delta"]
            content = delta.get("content")
            if content:
                print(content,end="",flush=True)#打字机效果，不换行，立即刷出
            print()#最后补个换行