#!/usr/bin/env python3
"""
Setup configuration for GVSA CLI application.

This module defines the package configuration for installing the GVSA CLI
as an executable command.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding='utf-8')

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip() 
        for line in requirements_file.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.startswith('#')
    ]

setup(
    name='gvsa-scrape',
    version='1.0.0',
    description='CLI tool for scraping and analyzing GVSA soccer data',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='GVSA Scraper',
    python_requires='>=3.8',
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'gvsa=cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
)

