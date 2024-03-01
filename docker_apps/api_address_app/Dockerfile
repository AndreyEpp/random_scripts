FROM python:3.11

RUN mkdir /api_address_app

WORKDIR /api_address_app

COPY requirements.txt .

RUN pip install -r requirements.txt

RUN apt-get update && \
    apt-get install wget default-mysql-client --yes && \
    mkdir -p ~/mysql && \
    wget "https://storage.yandexcloud.net/cloud-certs/CA.pem" \
         --output-document ~/mysql/root.crt && \
    chmod 0600 ~/mysql/root.crt


COPY . .

WORKDIR app

CMD gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000
