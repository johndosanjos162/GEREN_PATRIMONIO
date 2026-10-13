FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema para Numba/Kaleido
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY worker/ ./worker/
COPY App.py .
COPY .streamlit/ ./.streamlit/

# Cache Numba persistente
ENV NUMBA_CACHE_DIR=/app/__numba_cache__
RUN mkdir -p /app/__numba_cache__

EXPOSE 8501

CMD ["streamlit", "run", "App.py", "--server.port=8501", "--server.address=0.0.0.0"]
