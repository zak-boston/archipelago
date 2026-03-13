FROM python:3.12-slim

WORKDIR /app

RUN pip install flask wakeonlan --no-cache-dir

COPY app.py .
COPY static/ static/

EXPOSE 5000

CMD ["python", "app.py"]
