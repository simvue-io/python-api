FROM openfoam/openfoam10-paraview56
ARG simvue_file
USER root
RUN add-apt-repository ppa:deadsnakes/ppa -y
RUN apt-get update && \
    apt-get install -y python3.11-full
RUN useradd simvue -m
COPY . /simvue_client
RUN python3.11 -m ensurepip --upgrade
RUN python3.11 -m pip install /simvue_client
RUN python3.11 -m pip install -r /simvue_client/examples/OpenFOAM/requirements.txt
