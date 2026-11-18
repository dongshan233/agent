from typing import Annotated,Any, Callable,Literal,Optional,TypedDict

## 1
#Optional[x]≈kotlin的x?，表示x可以为None;3.10+更推荐 X|None 
def find(name:str)->Optional[str]:... #...：这是合法的对象 Ellipsis，放在函数体里当占位符，表示"只声明签名，不写实现"，
def find2(name:str)->str|None:...                      #类似 Kotlin 的抽象方法声明。这段代码是教学用的签名展示，不是能跑的完整函数。

## 2
#Literal:枚举取值
Role =Literal['admin','user','guest']

## 3
#TypedDict:类型字典，类似kotlin的data class
class Message(TypedDict):
    role:str
    content:str
#普通 dict[str, str] 只说明键值都是字符串，不约束有哪些键。
    # TypedDict 进一步声明：这个 dict 必须有 role 和 content 两个键，值都是 str。
    # 少键、多键、类型错，静态检查都会报。
#Kotlin 对照：形状上像 data class Message(val role: String, val content: String)，
    # 但本质完全不同——运行时 msg 就是个普通 dict，type(msg) 是 dict，访问方式是 msg["role"] 而不是 msg.role，
    # 也没有任何运行时校验（硬塞个错键进去，运行时不报错）。
#为什么不直接用 dataclass？因为 LLM 生态的数据交换格式就是 JSON/dict：
    # API 返回的 message 是 dict，json.loads 出来是 dict，LangGraph 的 state 也是 dict。
    # TypedDict 让你零转换成本地给这些 dict 加上类型提示。
#三者分工要记住：TypedDict = 只做静态标注、零运行时开销；
    # dataclass = 真正的类，有属性访问；Pydantic BaseModel = 真正的运行时校验（Agent 里定义工具入参用它）。
    # LangGraph 的 State 官方推荐写法就是 TypedDict。

## 4
#Annotated:在类型上挂元数据--LangGraph 的 State 里用它标注工具入参的元信息
from operator import add
class ChatState(TypedDict):
    message:Annotated[list[str],add]#新消息追加到旧列表后面
    count:int                         # 没挂reducer-》新的值直接覆盖旧值 
#节点返回 {"messages": [新消息]} 时，LangGraph 读取标注发现元数据是 add，就执行 旧列表 + 新列表（累积历史）；
# 没有 Annotated 的字段则是覆盖。LangChain 还提供现成的 add_messages reducer，比裸 add 更聪明（按消息 ID 去重更新）。
#例：Annotated[list, add_messages]  #list` 是真实类型，第二个参数是给框架看的「合并策略」元数据，运行时 Python 完全忽略它。

## 5
#泛型容器与Any
def first(items:list[str]) -> str | None:...
def parse(raw:dict[str,Any]) -> Any:...
#list[str] ≈ Kotlin List<String>，dict[str, Any] ≈ Map<String, Any>。
#Any 是个特殊值：任何类型都兼容它，它也兼容任何类型，等于对这块数据关闭类型检查。
# 注意它和 Kotlin 的 Any 不是一回事——Kotlin 的 Any 是所有类的根（≈ Java Object），
# 只能调它自带的方法；Python 的 Any 是"检查器放弃治疗"，标了 Any 的值随便点属性调方法都不报错。
# Python 里对应 Kotlin Any 角色的是 object。

#什么时候用 Any：解析来源不可控的 JSON（parse 就是典型——json.loads 的结果结构未知）。
# 原则是边界处用 Any 接进来，尽快转成具体类型或 Pydantic 模型，别让 Any 在代码里扩散。

## 6
#Callable --函数类型
Handler = Callable[[str],bool]
#读法：Callable[[参数类型列表], 返回类型]。这行 ≈ Kotlin 的 (String) -> Boolean。

#           Python                          Kotlin近似
#    str | None / Optional[str]             String?
#       Literal["a","b"]                      enum
#           TypedDict                       data class
#       Annotated[T, meta]               data class + 注解
#   list[str] / dict[str, Any]	        List<String> / Map<String, Any>
#           Any                         无直接对应（≠Kotlin Any）
#       Callable[[str], bool]              (String) -> Boolean