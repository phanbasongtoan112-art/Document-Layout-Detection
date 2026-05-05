# Use Python 3.10 slim as the base image
FROM python:3.10-slim

# Set environment variables to avoid interactive prompts and keep Python output clean
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# - poppler-utils: Required by pdf2image
# - libgl1 & libglib2.0-0: Required by opencv-python (fixes missing shared library errors)
# - wget & unzip: General utilities as requested
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    wget \
    unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements.txt first to leverage Docker cache for dependencies
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project into the container
# (Make sure .dockerignore prevents copying large data/ and predictions/ folders)
COPY . .

# Since this is a batch processing tool, we don't expose any ports.
# We leave the default command as bash, or you can override it at runtime.
CMD ["bash"]
