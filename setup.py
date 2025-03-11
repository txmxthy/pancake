from setuptools import setup

setup(
    name="pancake",
    author="Tim McDermott",
    version="0.1",
    py_modules=["pancake"],
    entry_points={
        "console_scripts": [
            "pancake=pancake:main",
        ],
    },
)