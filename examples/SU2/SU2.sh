#!/bin/bash
# Makes use of the SU2 tutorial: https://su2code.github.io/tutorials/Inviscid_ONERAM6/

export SU2_RUN=/home/wk9874/Documents/simvue/python-api/examples/SU2/bin
export PATH=$SU2_RUN:$PATH
export PYTHONPATH=$SU2_RUN:$PYTHONPATH

# Execute Simvue monitor
python3 SU2.py inv_ONERAM6.cfg
