FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY hf_space/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy broker source
COPY broker/ broker/
COPY memory/ memory/
COPY hf_space/app.py .

# Expose Gradio port
EXPOSE 7860

CMD ["python", "app.py"]
