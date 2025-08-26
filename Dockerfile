FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app

RUN apk add --no-cache ffmpeg

COPY requirements.txt .
RUN uv pip install -r requirements.txt --system

COPY . .

RUN mkdir cache

CMD gunicorn -k uvicorn.workers.UvicornWorker main:app -w ${WORKERS:-2} -b 0.0.0.0:80

