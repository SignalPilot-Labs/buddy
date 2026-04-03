# Runs once at startup to create/migrate database tables.
ARG PYTHON_VERSION=3.12

FROM python:${PYTHON_VERSION}-slim

WORKDIR /app

COPY db/pyproject.toml /app/db/pyproject.toml
COPY db/__init__.py /app/db/__init__.py
RUN pip install --no-cache-dir /app/db/

COPY db/ /app/db/
COPY config/ /app/config/

CMD ["python", "-m", "db.init"]
