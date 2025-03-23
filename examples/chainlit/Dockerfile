# Use the official Python 3.12 image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create the /app/files directory and set full permissions
RUN mkdir -p /app/.files && chmod 777 /app/.files
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Copy the current repository into the container
COPY . /app

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 7860

CMD python -m chainlit run app/app.py -w --host 0.0.0.0 --port 7860