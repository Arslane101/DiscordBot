FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a new user with a specific UID
RUN useradd -m -u 10001 appuser

# Switch to non-root user with a specific UID
USER 10001

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

WORKDIR /app

CMD ["python", "bot.py"]
