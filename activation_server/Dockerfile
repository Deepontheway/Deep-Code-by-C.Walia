FROM python:3.12-slim
WORKDIR /app
COPY activation_server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY activation_server ./activation_server
ENV ACTIVATION_DB=/data/activation.sqlite3
EXPOSE 8000
CMD ["sh", "-c", "uvicorn activation_server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
