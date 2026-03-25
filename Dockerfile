# Dockerfile
FROM python:3.10

# Instala Poetry y pip actualizado
RUN pip install --upgrade pip && pip install poetry

# Crea directorio de trabajo
WORKDIR /app

# Copia dependencias
COPY pyproject.toml poetry.lock* /app/

# Instala dependencias del proyecto (excepto xolo) sin crear virtualenv
RUN poetry config virtualenvs.create false && poetry install --no-root

# Copiar e instalar el paquete xolo desde el tar.gz (previamente generado con `poetry build`)
#COPY xolo-0.0.9a7.tar.gz /app/xolo-0.0.9a7.tar.gz
#RUN pip install /app/xolo-0.0.9a7.tar.gz

# Copia el código fuente
COPY xoloapi /app/xoloapi

# Expone el puerto
# EXPOSE 10000

# Comando por defecto: iniciar el API
# CMD ["uvicorn", "xoloapi.server:app", "--host", "0.0.0.0", "--port", "10000"]

