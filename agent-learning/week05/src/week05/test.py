
#消息分类

messages = [
    {"role":"system","content":"..."},
    {"role":"user","content":"苏州今天多少度"},

    #模型返回的第一条assistant消息：不带content，带tool_calls
    {"role":"assistant","content":None,"tool_calls":[
        {"id":"call_abc","type":"function","function":{"name":"get_weather","arguments":"{\"city\":\"苏州\"}"}}
    ]},

    #你执行函数后回填的tool消息：必须用上一步的id对应
    {"role":"tool","tool_call_id":"call_abc",
     "content":"{\"temp_c\":18,\"condition\":\"多云\"}"},
     #再发给模型 -> 模型返回带content的assistant回答
]

from pydantic import BaseModel,Field

class GetWeatherArgs(BaseModel):
    '''查询指定城市当前天气'''
    city:str = Field(description="城市名，中文如'苏州',拼音如'suzhou'")
    unit:str = Field(default="celsius",description="温度单位：celsius | fahrenheit")
#请求里新增tools字段，OpenAi兼容格式
tools = [{
    "type":"function",
    "function":{
        "nane":"get_weather",
        "description":"获取指定城市的当前天气（温度，天气状况）。当用户询问天气时使用。",
        "parameters":GetWeatherArgs.model_json_schema(),
    }
}]
