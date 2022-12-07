# SU2

This example is taken from https://su2code.github.io/tutorials/Inviscid_ONERAM6/.

Setup a Python virtual environment:
```
python3 -m venv venv
source ./venv/bin/activate
```
Install Simvue:
```
pip install simvue
```
Download and install the appropriate version of SU2, e.g. on Linux:
```
wget https://github.com/su2code/SU2/releases/download/v7.0.2/SU2-v7.0.2-linux64-mpi.zip
unzip SU2-v7.0.2-linux64-mpi.zip
```
Ensure that the environment variable `SU2_RUN` in the `SU2.sh` script is set to the `bin` directory created above.

Download the required config file and mesh file:
```
wget https://raw.githubusercontent.com/su2code/Tutorials/master/compressible_flow/Inviscid_ONERAM6/inv_ONERAM6.cfg
wget https://github.com/su2code/Tutorials/raw/master/compressible_flow/Inviscid_ONERAM6/mesh_ONERAM6_inv_ffd.su2
```
Execute the script:
```
. ./SU2.sh
```
