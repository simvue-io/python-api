#!/bin/bash
# Makes use of the SU2 tutorial: https://su2code.github.io/tutorials/Inviscid_ONERAM6/

export SU2_RUN=<set to SU2 bin directory>
export PATH=$SU2_RUN:$PATH
export PYTHONPATH=$SU2_RUN:$PYTHONPATH

# Execute SU2 & write PID to file
SU2_CFD inv_ONERAM6.cfg &
echo $! >/tmp/pid.file

# Execute Simvue monitor
python3 SU2.py /tmp/pid.file
