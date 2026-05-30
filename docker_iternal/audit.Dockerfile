FROM python:3.12-slim
LABEL authors="exizman"

WORKDIR /app

COPY ./auditapp/requirements.txt ./requirements.txt

RUN pip install -r requirements.txt
#TODO fix this

ENV PYTHONUNBUFFERED=1


ARG POSTGRES_USER
ARG POSTGRES_PASSWORD
ARG POSTGRES_PORT
ARG POSTGRES_NAME




ENV POSTGRES_USER=$POSTGRES_USER
ENV POSTGRES_PASSWORD=$POSTGRES_PASSWORD
ENV POSTGRES_HOST=$POSTGRES_HOST
ENV POSTGRES_PORT=$POSTGRES_PORT
ENV POSTGRES_NAME=$POSTGRES_NAME




#COPY ./authapp /app/authapp
#COPY ./db /app/db
#
#COPY ./common /app/common


#CMD ["uvicorn", "auth.run_web:app", "--host", "0.0.0.0", "--port", "8001"]