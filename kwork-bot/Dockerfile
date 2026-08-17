FROM python:3.11-slim

WORKDIR /app

# Зависимости, необходимые Playwright/Chromium для запуска в headless-режиме
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузер Chromium вместе с системными зависимостями,
# необходимыми Playwright.
RUN playwright install --with-deps chromium

COPY . .

CMD ["python", "main.py"]