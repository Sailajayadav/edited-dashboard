#!/usr/bin/env bash
set -e  # Stop on first error

echo "🚀 Installing Microsoft SQL Server ODBC Driver 17..."

# Install required tools
apt-get update && apt-get install -y curl gnupg apt-transport-https

# Add Microsoft GPG key
curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -

# Add Microsoft SQL Server repo
curl https://packages.microsoft.com/config/debian/11/prod.list \
    | tee /etc/apt/sources.list.d/mssql-release.list

# Install the driver + unixODBC
apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev

echo "✅ ODBC Driver installed successfully."

# Upgrade pip and install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
