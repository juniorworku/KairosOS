FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
RUN --mount=type=cache,target=/root/.cache/pip --mount=type=bind,source=wheelhouse,target=/wheels \
    if ls /wheels/*.whl > /dev/null 2>&1; then pip install --no-index --find-links=/wheels -r requirements.lock; \
    else pip install -r requirements.lock; fi
COPY app ./app
RUN pip install --no-cache-dir --no-deps . && useradd --create-home kairos
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
USER kairos
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
