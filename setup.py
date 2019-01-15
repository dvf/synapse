import setuptools

from electron import __version__ as version

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="electron-rpc",
    version=version,
    author="Daniel van Flymen",
    author_email="vanflymen@gmail.com",
    description="Rapid RPC Framework for your Python services using Asyncio + MsgPack",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/dvf/electron",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
