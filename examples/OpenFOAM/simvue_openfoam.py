import os
import re
import sys
import time

from simvue import Run

if __name__ == "__main__":
    # Regular expressions
    exp1 = re.compile(
        "^(.+):  Solving for (.+), Initial residual = (.+), Final residual = (.+), No Iterations (.+)$"
    )
    exp2 = re.compile("^ExecutionTime = ([0-9.]+) s")

    # Check the log file for new entries at this interval (in secs)
    polling_interval = 5

    run = Run()
    run.init(tags=["OpenFOAM"])

    running = True
    file_pos = 0
    ttime = None
    metrics = {}

    while running:
        # If log doesn't exist yet, wait for it
        if not os.path.isfile(sys.argv[1]):
            time.sleep(polling_interval)
            continue

        # Read log file
        with open(sys.argv[1], "r") as fh:
            fh.seek(file_pos)
            for line in fh.readlines():
                # Get time
                match = exp2.match(line)
                if match:
                    ttime = match.group(1)
                    if metrics:
                        run.log_metrics(metrics, time=ttime)
                        metrics = {}

                # Get metrics
                match = exp1.match(line)
                if match:
                    metrics["residuals.initial.%s" % match.group(2)] = match.group(3)
                    metrics["residuals.final.%s" % match.group(2)] = match.group(4)

            file_pos = fh.tell()

        # Check if application is still running
        if os.path.isfile(".finished"):
            running = False
        else:
            time.sleep(polling_interval)

    run.close()
