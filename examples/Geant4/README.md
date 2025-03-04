# Geant4 Example
[Geant4](https://geant4.web.cern.ch/) is a toolkit for the simulation of the passage of particles through matter. We will use Simvue to track repeating simulations of a proton fired at a target of beryllium, monitoring the yield of key particles of interest.

To run this example, run the Geant4 docker container:
```
docker run --rm -it artemisbeta/geant4:11.2.1
```
Then clone this repository, using recursive to also clone the Geant4 example submodule:
```
git clone --recursive https://github.com/simvue-io/python-api.git
```
Move into the example directory:
```
cd python-api/examples/Geant4
```
Create a virtual environment:
```
apt install python3.12-venv

python3 -m venv venv

source venv/bin/activate
```
Install requirements:
```
python3 -m pip install -r requirements.txt
```
Make a simvue.toml file - click Create New Run on the web UI, copy the contents listed, and paste into a config file using:
```
vi simvue.toml
```
Make and build the Geant4 binaries required:
```
cmake -DCMAKE_PREFIX_PATH=/usr/local/share/geant4/install/4.11.2/ -Bbuild FixedTarget/

cmake --build build
```
And then run the example:
```
python3 geant4_simvue.py build/MaterialTesting --events 10
```