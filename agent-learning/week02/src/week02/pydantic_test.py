from pydantic import BaseModel, Field,field_validator

class App(BaseModel):
    name:str
    package:str = Field(pattern=r"^[a-z][A-Z0-9_]*(\.[a-z0-9_]+)+$")

class Device(BaseModel):
    model:str
    os_version:str = Field(alias="osVersion",default="14")
    ram_gb:int = Field(gt = 0,le=64,description="RAM size in GB")
    apps:list[App] = []
    tags:set[str] = set()
    
    @field_validator("os_version")
    @classmethod
    def check_version(cls,v:str) -> str:
        if not v.isdigit():
            raise ValueError("版本号必须是数字字符串")
        return v