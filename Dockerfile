FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Editable install keeps the sources in /app, so the project root (fixtures/, migrations/)
# resolves exactly as it does on a developer machine.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY fixtures ./fixtures
COPY migrations ./migrations

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz').status == 200 else 1)"

CMD ["uvicorn", "src.adapters.inbound.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
