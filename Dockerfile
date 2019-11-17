FROM python:3.6-alpine

RUN adduser -D financial
WORKDIR /home/financial

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
RUN pip3 install gunicorn==19.9.0 pymysql==0.9.3

COPY app app
COPY migrations migrations
COPY financial.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP financial.py
ENV FLASK_ENV development

RUN chown -R financial:financial ./
USER financial

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]
