FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.lock
COPY app ./app
RUN pip install --no-cache-dir --no-deps . && useradd --create-home kairos
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
USER kairos
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
