FROM postgres:17-alpine
RUN apk add --no-cache python3 py3-pip && python3 -m venv /opt/backup
COPY deploy/backup/requirements.lock /tmp/requirements.lock
RUN /opt/backup/bin/pip install --no-cache-dir -r /tmp/requirements.lock
ENV PATH="/opt/backup/bin:$PATH"
WORKDIR /app
COPY deploy/backup/*.py ./
COPY backend/market/provider_secrets.py ./provider_secrets.py
ENTRYPOINT ["/opt/backup/bin/python"]
CMD ["/app/service.py"]
