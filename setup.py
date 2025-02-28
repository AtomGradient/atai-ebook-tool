# setup.py
from setuptools import setup, find_packages

setup(
    name='atai-ebook-tool',
    version='0.0.1',
    packages=find_packages(),
    install_requires=[
        "ebooklib",
        "beautifulsoup4"
    ],
    python_requires=">=3.6",
    entry_points={
        'console_scripts': [
            'atai-ebook-tool = atai_ebook_tool.cli:main',
        ],
    },
    description="A CLI tool to convert or extract text from e-books using ebook-convert",
    author="AtomGradient",
    author_email="alex@atomgradient.com",
    url="https://github.com/AtomGradient/atai-ebook-tool",
    license="MIT",  # Adjust as needed
)