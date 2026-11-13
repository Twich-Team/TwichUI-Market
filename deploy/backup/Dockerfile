FROM postgres:17-alpine
RUN apk add --no-cache python3
COPY worker.py /app/worker.py
ENTRYPOINT ["python3", "/app/worker.py"]
