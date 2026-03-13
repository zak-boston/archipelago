FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN pip install flask wakeonlan --no-cache-dir

COPY app.py .
COPY static/ static/

EXPOSE 5000

CMD ["python", "app.py"]
