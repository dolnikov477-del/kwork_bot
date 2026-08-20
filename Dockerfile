FROM python:3.11-slim
RUN apt-get update && apt-get install -y libglib2.0-0 libnss3 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 libxi6 libxtst6 libxrandr2 libasound2 libatk-bridge2.0-0 libgtk-3-0 libgbm1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium-headless-shell
COPY . .
ENTRYPOINT ["python", "main.py"]
