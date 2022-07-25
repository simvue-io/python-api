import re
import setuptools

with open('simtrack/__init__.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="simtrack",
    version=version,
    author="Andrew Lahiff",
    author_email="andrew.lahiff@ukaea.uk",
    description="Simulation tracking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/alahiff/simtrack-client",
    platforms=["any"],
    install_requires=["requests"],
    package_dir={'': '.'},
    packages=['simtrack'],
    package_data={"": ["README.md"]},
)
