from setuptools import setup, find_packages

setup(
    name="sgh-master",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "geopandas",
        "pandas",
        "numpy",
        "shapely",
        "lxml",
        "pyyaml",
        "requests",
        "tables",
        "sqlalchemy",
    ],
    python_requires=">=3.8",
) 