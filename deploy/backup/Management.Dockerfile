FROM postgres:17-alpine
RUN apk add --no-cache python3
WORKDIR /app
COPY management.py service.py ./
ENTRYPOINT ["python3", "/app/service.py"]
