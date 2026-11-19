
 # pydantic = **「dataclass + 运行时校验 + JSON 互转」

from pydantic import BaseModel, Field,field_validator
#1.BaseModel：所有模型的基类，提供__init__、__repr__、__eq__等方法,
#   自动校验，model_dump()、model_dump_json()、model_validate()、model_validate_json()等方法.
#2.Field：用于定义字段的元数据和验证规则，可以指定默认值、别名、描述、正则表达式等.
#3. field_validator：用于定义字段的自定义验证器，可以在字段赋值时进行额外的验证逻辑.

class App(BaseModel):
    name:str
    package:str = Field(pattern=r"^[a-z][A-Z0-9_]*(\.[a-z0-9_]+)+$")

class Device(BaseModel):
    model:str   #必填字符串
    os_version:str = Field(alias="osVersion",default="14") #默认值14， alias="osVersion"表示输入/输出 JSON 时字段名叫 osVersion，Python 内部仍用 os_version 访问。
    ram_gb:int = Field(gt = 0,le=64,description="RAM size in GB") #必须 > 0 且 <= 64 的整数；description 会写进自动生成的 JSON Schema，方便文档/API 工具展示。
    apps:list[App] = []
    tags:set[str] = set() #字符串集合，自动去重、无序；同样每个实例独立。

    #自定义校验器：可以有多个校验器作用于同一字段，按定义顺序执行。
    # 默认是 mode="after"：Pydantic 先完成类型转换（保证 v 是 str），再执行该函数。若想在转换前检查原始输入，用 @field_validator("os_version", mode="before")。
    @field_validator("os_version")#@field_validator("os_version") 指定只校验这个字段；也可以用 "*" 校验所有字段，或传多个字段名
    @classmethod  #@classmethod 是 v2 的固定写法，第一个参数是类 cls，第二个 v 是字段值。
    def check_version(cls,v:str) -> str:
        if not v.isdigit():
            raise ValueError("版本号必须是数字字符串")  #抛出 ValueError/AssertionError 会被 Pydantic 包装成 ValidationError；必须 return v，否则该字段会被置为 None。
        return v

 # 这段代码用声明式方式定义了设备数据结构：Field 负责正则、范围、别名和文档描述，类型注解负责转换与嵌套递归校验，
 # field_validator 补充业务规则（版本号必须是数字串），最终得到可自动校验、可导出 JSON Schema 的数据模型。



 ##解析与序列化
 
raw = {"model": "Pixel 8", "osVersion": "14", "ram_gb": 8,
       "apps": [{"name": "微信", "package": "com.tencent.mm"}]}

 # dict ->模型，校验失败的话抛出ValidationError异常
device = Device.model_validate(raw) 
print(device.os_version)

#模型 -> JSON 字符串
json_str = device.model_dump_json(exclude={"tags"}) 
#JSON 字符串 -> 模型
back = Device.model_validate_json(json_str)
#模型 -> dict
as_dict = device.model_dump()


##常用Field约束速查
Field(gt=0,le=100) # 数值范围  0<  <=100
Field(min_length=1,max_length=10) # 字符串长度范围
Field(pattern=r"^[a-z][A-Z0-9_]*(\.[a-z0-9_]+)+$") # 正则表达式
Field(default=...,description="...") # 必填字段，description 会写进 JSON Schema
Field(alias="xxx") # JSON 字段名映射
from typing import Optional
Optional[str]  # 可选类型，等价于 str | None;3.10+更推荐 X|None 
x:str|None
