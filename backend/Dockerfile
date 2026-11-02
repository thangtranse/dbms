FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=/app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser
CMD ["uvicorn", "ol.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
