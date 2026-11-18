from dataclasses import dataclass,field

class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def greet(self) ->str:
        return f"Hello, my name is {self.name} and I am {self.age} years old."

p = Person("Alice", 30)
print(p.greet())


#@dataclass自动生成__repr__(类似kotlin的tostring)和_eq_方法,按字段比较
@dataclass
class Device:
    model:str
    version:str='12'
    apps:list[str]=field(default_factory=list)

d= Device("Piexl 8")
print(d)
print(d==Device("Piexl 8"))