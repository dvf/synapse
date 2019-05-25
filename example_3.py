import asyncio
from time import sleep, time


async def say_something(what, delay, start_time):
    sleep(delay)
    print(f"{time() - start_time:.1f}s: {what}")


async def main():
    start_time = time()
    await say_something("hello", 2, start_time)
    await say_something("world", 3, start_time)


asyncio.run(main())
