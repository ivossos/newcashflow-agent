FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY cashflow_mcp_server.py .
COPY opera_client.py .
COPY server_http.py .

# Create data directory
RUN mkdir -p data

# Cloud Run uses PORT environment variable
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Run the HTTP server for Cloud Run
CMD ["python", "server_http.py"]
