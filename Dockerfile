# Imagen de producción para la API de LATIO Kit (src/api.py).
# No incluye toolkit-api/ (el explorador estático se sirve aparte, hoy vía
# GitHub Pages — ver .github/workflows/deploy.yml y README.md) ni el
# pipeline de extracción completo (data/raw/ son ~7.5MB de texto legal,
# solo necesarios para regenerar data/processed/, no para servir la API).

FROM python:3.12-slim AS base

# Coincide con la versión de Python contra la que se verificó
# requirements-prod.txt (uvicorn 0.35.0 corrió bajo Python 3.12.3 al
# preparar este despliegue) — no cambiar sin re-verificar.

WORKDIR /app

# Dependencias primero, para aprovechar la cache de capas de Docker: solo
# se reinstalan si requirements-prod.txt cambia, no en cada cambio de código.
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Código de la aplicación. Nota: la API (src/api.py) sirve /v1/reasoning/*
# (no depende de datos externos) y /v1/corpora/* (lee reports/manifest.json
# y data/processed/*.json, que si existen en la imagen se sirven; si no
# existen, esos endpoints devuelven 404/lista vacía, no rompen el arranque).
COPY src/ src/
COPY reports/manifest.json reports/manifest.json
COPY data/processed/ data/processed/

# Usuario sin privilegios — no correr la API como root en producción.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
# LATIO_ALLOWED_ORIGINS: lista de orígenes CORS separada por comas (ver
# src/api.py). Sin definir, usa el default de desarrollo — SIEMPRE pasar
# esta variable en el despliegue real (ver DEPLOYMENT.md).
ENV LATIO_ALLOWED_ORIGINS=""

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
