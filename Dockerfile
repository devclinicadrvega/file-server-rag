FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

RUN mkdir -p /data

EXPOSE 8002

ENTRYPOINT ["./entrypoint.sh"]
