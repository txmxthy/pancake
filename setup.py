from setuptools import setup

setup(
    name="pancake",
    version="1.0.3",
    author="Tim McDermott",
    py_modules=["pancake"],
    install_requires=[
        "tqdm",
    ],
    entry_points={
        "console_scripts": [
            "pancake=pancake:main",
        ],
    },
)