from setuptools import setup, find_packages

setup(
    name="vic-fix-pro",
    version="1.0.0",
    description="A powerful, lightning-fast desktop application for media processing (MKVToolNix clone).",
    author="Vic",
    packages=find_packages(),
    install_requires=[
        "customtkinter>=5.2.2",
        "numpy>=1.26.0",
        "scipy>=1.11.0"
    ],
    entry_points={
        "console_scripts": [
            "vicfix=app:VicFixApp"
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
