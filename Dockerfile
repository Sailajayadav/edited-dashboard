# Use slim Python base image
FROM python:3.11-slim

# Install ODBC Driver 17 for SQL Server
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list \
       | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your Flask app
COPY . .

# Expose port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]
