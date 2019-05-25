# What are coroutines?

Coroutines are functions that can be paused. We define them using the `async` syntax:

```python
async def say_something(what):
    print(what)
```

But coroutines can't be run directly:

```
>>> say_something("hello")
<coroutine object say_something at 0x1069837c8>
```

Calling a coroutine won't execute it—coroutines need to be *scheduled* to be executed.

# Event Loops

An event loop is just that—a continuously running loop that checks if an async function is done being paused. In Python (unlike JavaScript) we create the event loop explicitly:

```python
import asyncio

loop = asyncio.get_event_loop()
```

`get_event_loop()` will get or create the event loop in the current thread. We must schedule our `say_something` coroutine on the event loop if we wish to run it.

```python
import asyncio


async def say_something(what):
    print(what)


loop = asyncio.get_event_loop()
task = loop.create_task(say_something("hello world"))

loop.run_until_complete(task)
# hello world
```

A much easier way to run coroutines was added in Python 3.7—using `asyncio.run()`. The following is equivalent to the above example:

```python
import asyncio


async def say_something(what):
    print(what)


asyncio.run(say_something("hello world"))
```

`asyncio.run()` will create the event loop, run our coroutine, and kill the loop once done.


 # Concurrency
 
 TBA
 