import asyncio
import time


async def say_after(delay, what, elapsed):
    await asyncio.sleep(delay)
    print(f"{time.monotonic() - elapsed:.2f}s: {what}")


async def main():

    started = time.monotonic()

    # await say_after(2, "hello", started)
    # await say_after(4, "world", started)

    task1 = asyncio.create_task(say_after(2, 'hello', started))
    task2 = asyncio.create_task(say_after(4, 'world', started))

    await task1
    await task2
    # await asyncio.gather(
    #     say_after(2, "hello", started),
    #     say_after(4, "world", started),
    # )
    print(f"finished at {time.monotonic() - started:.2f}s")


asyncio.run(main())
