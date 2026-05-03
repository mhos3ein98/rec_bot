# =============================================================================
# Dockerfile
# Build : docker build -t rec_bot .
# Run   : docker run -d --name rec_bot --restart unless-stopped \
#           -v $(pwd)/data:/app/data rec_bot
# =============================================================================

FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

VOLUME ["/app/data"]
CMD ["python", "bot.py"]
