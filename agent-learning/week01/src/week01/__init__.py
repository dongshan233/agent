def main() -> None:
    flow()

def text(message: str="hello uv") -> None:
    nums = [1, 2, 3,5,6,7,8]
    doubled = [x*2 for x in nums]
    positives = [x for x in nums if x > 3]
    both = [x*2 for x in nums if x > 3]
    pairs = [len(w) for w in ['Hello', 'World', 'Python']]
    print(" Doubled:", doubled)
    print(" Positives:", positives)
    print(" Both:", both)
    print(" Pairs:", pairs)
    print(message)

def flow() -> None:
    nums = [1, 2, 3, 4, 5]
    for i,n in enumerate(nums):
        print(f"Index: {i}, Value: {n}")

    while True:
        cmd = input("Enter a command (type 'exit' to quit): >")
        if cmd.lower() == 'exit':
            print("Exiting the loop.")
            break
        else:
            print(f"You entered: {cmd}")