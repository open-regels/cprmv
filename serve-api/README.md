## CPRMV serve API

Experimental and WIP

### installation

requires python, FastAPI and rdflib

`pip install FastAPI`
`pip install rdflib`

### usage

run:

`fastapi dev cprmv-serve.py`

then navigate with a browser to: http://127.0.0.1/docs
to try out the API

## Docker Setup Synology NAS

### Build the Docker Image
From your project folder:

`cd /volume2/development/cprmv/serve-api/`
`docker build -t cprmv-fastapi .`

### Run the Docker Container

`docker run -d --name cprmv-api -p 8000:8000 cprmv-fastapi`

App will be available at: http://<NAS-IP>:8000/

#### Basic Docker Commands
- **Stop**: docker stop cprmv-api
- **Start**: docker start cprmv-api
- **Logs**: docker logs -f cprmv-api
- **Remove**: docker rm -f cprmv-api

## Optional: Docker Compose (for Persistence & Autostart)

### Docker Compose File

Create `/volume2/docker/projects/cprmv/serve-api/compose.yml`

```
version: "3.8"

services:
  cprmv-api:
    container_name: cprmv-api
    build: .
    ports:
      - "8000:8000"
    restart: unless-stopped
```