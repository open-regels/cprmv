## CPRMV serve API

Experimental and WIP ...

### installation

requires python, FastAPI, rdflib and lxml

`pip install FastAPI`
`pip install rdflib`
`pip install parse`
`pip install lxml`

### Testing

Make sure pytest is installed:
`pip install pytest`

Then from the directory containing this README and serve.py run:
`python -m pytest -vv`

### usage

Host locally:

`fastapi dev serve.py`

then navigate with a browser to: http://127.0.0.1/docs
to try out the API

## Docker Setup Synology NAS

### Build the Docker Image
From your project folder:

`cd /volume2/development/cprmv/serve-api/`<br>
`docker build -t cprmv-fastapi .`

### Run the Docker Container

`docker run -d --name cprmv-api -p 8000:8000 cprmv-fastapi`

App will be available at: http://{NAS-IP}:8000/

#### Basic Docker Commands
- **Stop**: docker stop cprmv-api
- **Start**: docker start cprmv-api
- **Logs**: docker logs -f cprmv-api
- **Remove**: docker rm -f cprmv-api

## Optional: Docker Compose (for Persistence & Autostart)

`cd /volume2/development/cprmv/serve-api/`<br>
`docker-compose up -d --build`

### How This Works
- The .xsl file should go in `/volume2/docker/cprmv/` on Synology NAS.
- Inside the container, these files will be available at /app/data/.



