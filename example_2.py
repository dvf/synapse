import asyncio


async def say_something(what):
    print(what)


asyncio.run(say_something("hello world"))
