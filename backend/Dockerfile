# Backend image
FROM python:3.12-slim

WORKDIR /app

# Install packages first, so code changes don't redo this slow step
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code and docs/ (.dockerignore keeps out .env and databases)
COPY . .

# Folder for the SQLite database volume
RUN mkdir -p /app/data

EXPOSE 8000

# 0.0.0.0 lets other containers and your browser reach the API
CMD [ "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

