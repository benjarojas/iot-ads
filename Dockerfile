FROM python:3.12-slim

WORKDIR /app

# TF_VARIANT selects the TensorFlow build: "cpu" (default) or "gpu".
#   docker build --build-arg TF_VARIANT=gpu .   # tensorflow[and-cuda]
# Run a GPU image with NVIDIA Container Toolkit: docker run --gpus all ...
ARG TF_VARIANT=cpu

COPY requirements.txt requirements-cpu.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements-${TF_VARIANT}.txt

COPY . .
