FROM python:3.12-slim

WORKDIR /app

# Install system dependencies that might be needed for rdflib
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --timeout=300 fastapi uvicorn[standard] rdflib parse lxml

COPY cprmv-serve.py .

EXPOSE 8000

CMD ["uvicorn", "cprmv-serve:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
