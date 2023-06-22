FROM python:3.9-slim

WORKDIR /app

# Install required packages for building hnswlib
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential poppler-utils tesseract-ocr-all libmagic1 \
    g++ git \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Download the model files and cache them in Docker image
RUN python -c "from transformers import AutoModel, AutoTokenizer; AutoTokenizer.from_pretrained('bert-base-uncased'); AutoModel.from_pretrained('bert-base-uncased')"
RUN python -c "from transformers import GPT2TokenizerFast; GPT2TokenizerFast.from_pretrained('gpt2')"