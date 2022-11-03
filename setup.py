import re
import setuptools

with open('simvue/__init__.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', fd.read(), re.MULTILINE).group(1)

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="simvue",
    version=version,
    author="Andrew Lahiff",
    author_email="andrew.lahiff@ukaea.uk",
    description="Simulation tracking and monitoring",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/simvue-io/client",
    platforms=["any"],
    install_requires=["requests", "randomname", "msgpack", "tenacity"],
    package_dir={'': '.'},
    packages=["simvue"],
    package_data={"": ["README.md"]},
    scripts=["bin/simvue_sender"]
)
