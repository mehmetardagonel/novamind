# Backend Dockerfile (Python FastAPI + ML Models)
FROM python:3.12-slim

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları (ML modelleri için gerekli)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala
COPY requirements.txt .

# Bağımlılıkları yükle
RUN pip install --no-cache-dir -r requirements.txt

# Backend kodunu kopyala
COPY . .

# ML modellerinin olduğunu kontrol et
RUN if [ -d "ml_model/models" ]; then \
    echo "✅ ML models found"; \
    else \
    echo "⚠️  Warning: ML models not found in ml_model/models/"; \
    fi

# Port
EXPOSE 8001

# Güvenlik için non-root user
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Health chec
#HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
 #   CMD python -c "import requests; requests.get('http://localhost:8001/health', timeout=2)" || exit 1

# FastAPI başlat
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
