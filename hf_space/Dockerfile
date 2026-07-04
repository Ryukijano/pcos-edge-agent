FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY hf_space/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy broker source, memory, and cloud provider
COPY broker/ broker/
COPY memory/ memory/
COPY models/cloud/ models/cloud/
COPY hf_space/app.py .

# Environment defaults
ENV PCOS_BROKER_HOST=0.0.0.0
ENV PCOS_BROKER_PORT=7860
ENV PCOS_LOG_JSON=true

# Expose Gradio port
EXPOSE 7860

CMD ["python", "app.py"]
