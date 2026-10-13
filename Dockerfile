# Dockerfile
FROM python:3.10

ARG XOLO_VERSION=development
LABEL org.opencontainers.image.title="Xolo API" \
      org.opencontainers.image.version="${XOLO_VERSION}" \
      org.opencontainers.image.source="https://github.com/nachocode/xolo"

# Keep image dependency resolution aligned with CI and release jobs.
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir poetry==2.2.1

# Crea directorio de trabajo
WORKDIR /app

# Copy dependency metadata and the monorepo-local xolo package.
COPY pyproject.toml poetry.lock* /app/
COPY xolo-client/pyproject.toml /app/xolo-client/pyproject.toml
COPY xolo-client/README.md /app/xolo-client/README.md
COPY xolo-client/xolo /app/xolo-client/xolo

# Install dependencies without creating a virtualenv. The API consumes the
# exact xolo-client source from this monorepo commit.
RUN poetry config virtualenvs.create false && poetry install --only main --no-root --no-interaction

# Copia el código fuente
COPY xoloapi /app/xoloapi
COPY scripts /app/scripts

# Expone el puerto
# EXPOSE 10000

# Comando por defecto: iniciar el API
CMD ["uvicorn", "xoloapi.server:app", "--host", "0.0.0.0", "--port", "10000"]
