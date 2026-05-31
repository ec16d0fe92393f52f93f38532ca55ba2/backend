FROM python:3.12-slim
LABEL authors="exizman"

WORKDIR /app

COPY ./gamificationapp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
