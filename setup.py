from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="deployer",
    version="0.1.0",
    author="Renato Critelli",
    author_email="renato.critelli.ifusp@gmail.com",
    description="Python package to create deploy scripts for algo trading",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/seu_usuario/deployer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    include_package_data=True,
    package_data={
        "deployer": ["config/*.json"],
    },
)