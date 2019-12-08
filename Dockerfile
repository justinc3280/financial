FROM python:3.6-alpine

RUN adduser -D financial
WORKDIR /home/financial

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN apk add gcc musl-dev python3-dev libffi-dev openssl-dev
RUN pip3 install gunicorn==19.9.0 cryptography==2.8

COPY app app
COPY migrations migrations
COPY financial.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP financial.py
ENV FLASK_ENV development

RUN chown -R financial:financial ./
USER financial

ENTRYPOINT ["./boot.sh"]
