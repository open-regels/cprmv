FROM python:3.12-bookworm

WORKDIR /app

# Install Dutch locale
RUN apt-get update && apt-get install -y locales && \
    sed -i '/nl_NL.UTF-8/s/^# //g' /etc/locale.gen && \
    locale-gen && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for locale
ENV LANG=nl_NL.UTF-8
ENV LANGUAGE=nl_NL:nl
ENV LC_ALL=nl_NL.UTF-8

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies with more specific pip options
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --timeout=300 --retries=3 -r requirements.txt

# Copy application code
COPY serve.py .
COPY data/ ./data/

EXPOSE 8000

CMD ["fastapi", "run", "serve.py", "--port", "8000"]
