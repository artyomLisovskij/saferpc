FROM ghcr.io/nevillegrech/gigahorse-toolchain:latest
USER root

RUN apt-get update && apt-get install -y python3-pip

RUN pip install fastapi uvicorn
WORKDIR /app
COPY rpc.py /app/rpc.py
ENTRYPOINT  ["uvicorn", "rpc:app", "--host", "0.0.0.0", "--port", "8000"]