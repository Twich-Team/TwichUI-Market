FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/market ./market
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home market
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
COPY backend/tests ./tests
COPY contracts /contracts
USER market
EXPOSE 8000
CMD ["uvicorn", "market.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
