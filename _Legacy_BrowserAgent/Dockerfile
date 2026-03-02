# Dockerfile for Browser Agent - Bedrock AgentCore Runtime
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY browser_session_manager.py .
COPY browser_agent.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NOVA_ACT_API_KEY=b9863c14-b44c-48c0-ac9b-ae870ca59e79

# Expose port for AgentCore Runtime
EXPOSE 8080

# Start the AgentCore server by running the module
# This will import the module and start the HTTP server
CMD ["python", "-c", "from browser_agent import app; app.run()"]
