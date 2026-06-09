FROM python:3.11-slim

WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# PERBAIKAN UTAMA:
# Bersihkan sisa-sisa kemasan google yang corrupt bawaan OS, upgrade pip, 
# lalu pasang requirements secara paksa agar namespace google ter-render ulang dengan bersih.
RUN pip install --no-cache-dir --upgrade pip && \
    pip uninstall -y google google-generativeai protobuf && \
    pip install --no-cache-dir -r requirements.txt --force-reinstall

# Copy the rest of the application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]