from pydantic import BaseModel,Field,ValidationError,model_validator
import json
import sys

class InstallApp(BaseModel):
    name:str=Field(min_length=1,examples=["微信"]) #必填字符串，最小长度1，example会写进自动生成的 JSON Schema，方便文档/API 工具展示。
    package:str=Field(pattern=r"^[a-z][\w]*(\.[\w]+)+$",examples=["com.tencent.mm"]) #必填字符串，正则约束包名格式，example会写进自动生成的 JSON Schema，方便文档/API 工具展示。
    version:str|None = None
class DeviceInfo(BaseModel):
    model:str = Field(min_length=1,examples=["Pixel 8"]) 
    os_version:str = Field(alias="osVersion",pattern=r"^\d+(\.\d+)*$")
    ram_gb:int = Field(gt=0,le=64,description="RAM size in GB")
    battery_pct:int = Field(default = 100,gt=0,le=100)
    screen_size_in:float=Field(gt=4,le=9)
    apps:list[InstallApp]=[]#必填字符串，最小长度1，example会写进自动生成的 JSON Schema，方便文档/API 工具展示。

    @model_validator(mode="after")
    def is_flagship(self)->"DeviceInfo":
        if self.ram_gb>=8 and "Pro" in self.model:
            return self
        raise ValueError("旗舰机要求 ram_gb >= 8 且 model 包含 'Pro'")

SAMPLE = """
   {"model": "Pixel 8", "osVersion": "14", "ram_gb": 8,
 "apps": [{"name": "微信", "package": "com.tencent.mm"},
          {"name": "Chrome", "package": "com.android.chrome", "version": "120"}]}
"""

def main()-> None:
    #正确使用
    try:
        device =DeviceInfo.model_validate_json(SAMPLE)
        print(f"设备：{device.model} / Android {device.os_version} / {device.ram_gb}GB")
        print(f"应用（{len(device.apps)}）:"+",".join(a.name for a in device.apps))
        print("schema 片段",DeviceInfo.model_json_schema())
    except ValidationError as e:
        print("校验失败:", e)
    #错误使用
    bad = '{"model": 123, "osVersion": "v14", "ram_gb": -8, "apps": [{"name": "", "package": "bad"}]}'
    try:
        DeviceInfo.model_validate_json(bad)
    except ValidationError as e:
        print("\n校验失败明细")
        for err in e.errors():
            print(f" {'.'.join(str(x) for x in err['loc'])}:{err['msg']} (type={err['type']})")
        sys.exit(1)
if __name__ == "__main__":
    main()