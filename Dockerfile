FROM ghcr.io/astral-sh/uv:python3.12-alpine

WORKDIR /app
COPY requirements.txt .

RUN uv pip install -r requirements.txt --system

COPY . .
CMD ["uv", "run", "main.py"]
