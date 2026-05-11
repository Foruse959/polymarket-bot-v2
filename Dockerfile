FROM python:3.11-slim

WORKDIR /app

# Unbuffered Python output — makes logs appear in Railway immediately
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "app.py"]
