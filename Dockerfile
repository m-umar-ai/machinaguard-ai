# Works on Hugging Face Spaces (Docker SDK), Render, Railway, Fly.io, Google Cloud Run
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Pre-train the anomaly model at build time so first load is fast
RUN python -m ml.train_model || true
EXPOSE 7860
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-7860} --server.address=0.0.0.0"]
