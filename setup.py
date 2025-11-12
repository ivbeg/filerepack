import re
import io
import codecs
from setuptools import setup, find_packages

open_as_utf = lambda x: io.open(x, encoding='utf-8')

(__version__, ) = re.findall("__version__.*\s*=\s*[']([^']+)[']",
                             open('filerepack/__init__.py').read())

def long_description():
    with codecs.open('README.md', encoding='utf8') as f:
        return f.read()

readme = long_description()

history = open_as_utf('HISTORY.md').read()



setup(
    name='filerepack',
    version=__version__,
    description="Repacks existing (un)compressed files for higher compression",
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',    
    author='Ivan Begtin',
    author_email='ivan@begtin.tech',
    url='https://github.com/ivbeg/filesrepack',
    packages=find_packages(exclude=('tests', 'tests.*')),
    include_package_data=True,
    install_requires=[
        'typer>=0.9.0',
    ],
    extras_require={
        'parquet': ['duckdb>=0.9.0'],
    },
    entry_points={
        'console_scripts': [
            'filerepack = filerepack.__main__:main',
        ],
    },
    license="BSD",
    zip_safe=False,
    keywords='files converter compression',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ]
)
