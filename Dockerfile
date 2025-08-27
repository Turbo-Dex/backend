FROM python:3.11-slim

WORKDIR /app

# petit script de test
COPY test.py .

CMD ["python", "test.py"]
