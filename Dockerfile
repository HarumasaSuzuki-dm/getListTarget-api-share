# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt /app/requirements.txt

# 例: requirements.txtで Playwright==1.35.0 を指定しておく
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app

ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
