# setup.py

from setuptools import setup, find_packages

setup(
    name="sawmill-edge-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "asyncua>=1.0.0",
        "paho-mqtt>=1.6.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.1.0"
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.4",
            "pytest-asyncio>=0.23.5",
            "pytest-cov>=6.0.0",
            "httpx>=0.28.0"
        ]
    }
)