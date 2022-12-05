import re
import setuptools

with open('simvue/__init__.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="simvue",
    version=version,
    author_email="info@simvue.io",
    description="Simulation tracking and monitoring",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://simvue.io",
    platforms=["any"],
    install_requires=["requests", "msgpack", "tenacity", "pyjwt", "psutil"],
    package_dir={'': '.'},
    packages=["simvue"],
    package_data={"": ["README.md"]},
    scripts=["bin/simvue_sender"]
)
