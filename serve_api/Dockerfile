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

# Copy the entire src directory including any subdirectories like utils
COPY src/ ./src/
COPY data/ ./data/
COPY respec/ ./respec/

# Add labels for better Docker Hub integration
LABEL maintainer="Bas.Kaptijn@ictu.nl"
LABEL description="CPRMV Rules Serve API - Experimental API for fetching CPRMV Rules from RuleSets"
LABEL version="0.4.1"
LABEL org.opencontainers.image.source="https://git.open-regels.nl/standards/cprmv"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check using built-in urllib (no external dependencies)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8000/', timeout=5)" || exit 1
  
CMD ["fastapi", "run", "src/serve.py", "--port", "8000", "--host", "0.0.0.0"]
