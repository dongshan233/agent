import json
import sys
from pathlib import Path



STORE = Path(__file__).with_name("todo.json")

def load()->list[dict]:
    if not STORE.exists():
        return []
    return json.loads(STORE.read_text(encoding="utf-8"))

def save(items:list[dict])->None:
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def add(text:str)->None:
    items =load()
    items.append({"id":max((i["id"] for i in items), default=0)+1, "text":text,"done":False})
    save(items)
    print(f"已添加: #{items[-1]['id']} {text}")

def show()->None:
    items = load()
    if not items:
        print("没有待办事项。")
        return
    for item in items:
        status = "✔" if item["done"] else "✘"
        print(f"#{item['id']} [{status}] {item['text']}")
def set_done(item_id:int,done:bool)->None:
    items=load()
    for it in items:
        if it["id"]==item_id:
            it["done"]=done
            save(items)
            print(f"已更新: #{it['id']} {it['text']} 状态为 {'完成' if done else '未完成'}")
            return
    print(f"未找到ID为 {item_id} 的待办事项。")

def delete(item_id:int)->None:
    items=load()
    for i,it in enumerate(items):
        if it["id"]==item_id:
            del items[i]
            save(items)
            print(f"已删除: #{it['id']} {it['text']}")
            return
    print(f"未找到ID为 {item_id} 的待办事项。")

def main() -> None:
    if len(sys.argv)<2:
        show()
        return
    cmd,*args=sys.argv[1:]
    if cmd=="add" and args:
        add(" ".join(args))
    elif cmd=="list":
        show()
    elif cmd=="done" and args:
        set_done(int(args[0]),True)
    elif cmd=="del" and args:
        delete(int(args[0]))
    else:
        print("用法: todo.py add <内容> | list | done <id> | del <id>")

if __name__ == "__main__":
    main()