FROM continuumio/miniconda3

WORKDIR /app

COPY . ./
# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]

RUN apt-get update && apt-get install -y \
    gnupg \
    apt-transport-https \
    software-properties-common \
    ca-certificates \
    dirmngr \
    gcc \
    g++

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 3FA7E0328081BFF6A14DA29AA6A19B38D3D831EF
RUN echo "deb https://download.mono-project.com/repo/debian stable-buster main" | tee /etc/apt/sources.list.d/mono-official-stable.list

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    bash \
    monodevelop \
    msbuild \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/Pulsatile_Model/
COPY Pulsatile_Model .
RUN msbuild "Blood Flow Model.sln"
RUN chmod +x "Blood Flow Model/bin/Debug/BloodflowModel.exe"

WORKDIR /app/

# Initialize conda in bash config files:
RUN conda init bash
RUN conda update -n base -c defaults conda -y

# Create the environment:
RUN conda create -n bloodflow -c conda-forge python=3.9 -y

# Activate the environment, and make sure it's activated:
RUN echo "conda activate bloodflow" > ~/.bashrc

# ensure the installation is working and pip is available
RUN python3.9 -m pip install pip --user
RUN python3.9 -m pip install --upgrade pip distlib wheel setuptools cython

RUN cd /app/ && python3.9 -m pip install --no-cache-dir ./in-silico-trial
RUN cd /app/ && python3.9 -m pip install --no-cache-dir .
RUN export DIJITSO_CACHE_DIR=/patient/.cache

COPY . .

ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "bloodflow", "python3.9", "API.py"]

