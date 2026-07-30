import contextvars
from concurrent.futures import ThreadPoolExecutor

v = contextvars.ContextVar('v', default="none")

def worker():
    print("Worker sees:", v.get())

def main():
    v.set("hello")
    with ThreadPoolExecutor() as e:
        ctx = contextvars.copy_context()
        e.submit(ctx.run, worker).result()

main()
