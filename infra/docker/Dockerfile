FROM python:3.12-slim

ARG SERVICE_DIR
WORKDIR /app

# Preserve the real repo layout (services/<name>/app/main.py, tools/...) instead of
# flattening the service into /app, because some services compute their repo root as
# Path(__file__).resolve().parents[3] and import shared code from tools/ at that root.
COPY ${SERVICE_DIR}/requirements.txt ./${SERVICE_DIR}/requirements.txt
RUN pip install --no-cache-dir -r ${SERVICE_DIR}/requirements.txt

COPY ${SERVICE_DIR}/ ./${SERVICE_DIR}/
COPY tools/ ./tools/

WORKDIR /app/${SERVICE_DIR}

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
