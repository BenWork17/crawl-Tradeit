FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --worker-class gthread --workers 1 --threads 8 --timeout 120 --graceful-timeout 30 web_app:app"]
