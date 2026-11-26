FROM python:3.14-bookworm@sha256:fbaf91204f2758a70a7f7d6cf3c2871851227152a54e6a7b5b59941c4566b6b5

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
RUN pip install --no-cache-dir --timeout=300 --retries=3 --require-hashes --no-deps -r requirements.txt

# Copy the entire src directory including any subdirectories like utils
COPY src/ ./src/
COPY data/ ./data/
COPY respec/ ./respec/
COPY methods/ ./methods/
# Bundled certSIGN Web CA intermediate, loaded by src/serve.py into its SSL context.
# repository.officiele-overheidspublicaties.nl omits this intermediate from its TLS
# handshake, so without it OpenSSL/Python cannot verify the chain. See certs/README
# and SSL_FIX.md for provenance and details.
COPY certs/ ./certs/

# Build metadata, reported by GET /health
ARG BUILD_SHA
ARG BUILD_RUN
ENV BUILD_SHA=$BUILD_SHA BUILD_RUN=$BUILD_RUN

# Image metadata (OCI labels); the image is published to ghcr.io/open-regels/cprmv-api.
LABEL maintainer="Bas.Kaptijn@ictu.nl"
LABEL description="CPRMV Rules Serve API - Experimental API for fetching CPRMV Rules from RuleSets"
LABEL org.opencontainers.image.version="0.4.3"
LABEL org.opencontainers.image.source="https://github.com/open-regels/cprmv"
LABEL org.opencontainers.image.revision=$BUILD_SHA

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check using built-in urllib (no external dependencies)
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://localhost:8000/health', timeout=5)" || exit 1

CMD ["fastapi", "run", "src/serve.py", "--port", "8000", "--host", "0.0.0.0"]
