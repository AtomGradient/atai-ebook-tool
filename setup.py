# setup.py
from setuptools import setup, find_packages

setup(
    name='atai-ebook-tool',
    version='0.0.2',
    packages=find_packages(),
    install_requires=[
        "ebooklib",
        "beautifulsoup4",
        "mobi"
    ],
    python_requires=">=3.6",
    entry_points={
        'console_scripts': [
            'atai-ebook-tool = atai_ebook_tool.cli:main',
        ],
    },
    description="A command-line tool for parsing ebooks (such as EPUB and MOBI) and converting them into a structured JSON file.",
    author="AtomGradient",
    author_email="alex@atomgradient.com",
    url="https://github.com/AtomGradient/atai-ebook-tool",
    license="MIT",  # Adjust as needed
)