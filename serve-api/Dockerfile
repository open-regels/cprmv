FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy source code and requirements
COPY requirements.txt .
COPY cprmv-serve.py .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "cprmv-serve:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
