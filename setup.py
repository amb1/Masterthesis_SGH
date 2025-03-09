from setuptools import setup, find_packages

setup(
    name="local",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "geopandas>=0.9.0",
        "shapely>=1.7.1",
        "owslib>=0.25.0",
        "pyyaml>=5.4.1",
        "lxml>=4.9.0",
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "simpledbf>=0.2.6"
    ]
) 