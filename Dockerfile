FROM python:3.12-slim

WORKDIR /app

# TF_VARIANT selects the TensorFlow build: "cpu" (default) or "gpu".
#   docker build --build-arg TF_VARIANT=gpu .   # tensorflow[and-cuda]
# Run a GPU image with NVIDIA Container Toolkit: docker run --gpus all ...
ARG TF_VARIANT=cpu

COPY requirements.txt requirements-cpu.txt requirements-gpu.txt ./
RUN pip install --no-cache-dir -r requirements-${TF_VARIANT}.txt

# For the GPU build, tensorflow[and-cuda] installs the CUDA libs under
# site-packages/nvidia/*/lib but does not put them on the loader path in a slim
# base image. Register every nvidia/*/lib dir with ldconfig so TensorFlow can
# dlopen cuDNN/cuBLAS/etc. (No-op for the CPU build — the nvidia package is absent.)
RUN if [ "$TF_VARIANT" = "gpu" ]; then \
      python -c "import os,glob,nvidia; print('\n'.join(glob.glob(os.path.dirname(nvidia.__file__)+'/*/lib')))" \
        > /etc/ld.so.conf.d/nvidia-cuda.conf && ldconfig; \
    fi

COPY . .
