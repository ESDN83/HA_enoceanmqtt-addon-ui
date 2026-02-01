# HA_enoceanmqtt-addon-ui Technical Todos/Checklist

## Global Setup
- [ ] Install Python 3.11, FastAPI, uvicorn, lxml, jinja2
- [ ] Create HA_enoceanmqtt-addon-ui/addon/ directory structure
- [ ] Copy icon/logo from slim/original

## Phase 1: HA Addon Setup
- [ ] Write addon/config.yaml (slug="enocean-config-ui", ingress port 8000, map config:rw)
- [ ] Write addon/Dockerfile (python:3.11-slim, COPY rootfs/app /app, RUN pip install -r requirements.txt)
-