# Frontend image: the Streamlit chat app
FROM python:3.12-slim

WORKDIR /app

# Install packages first, so code changes don't redo this step
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# 0.0.0.0 lets your browser reach the app from outside the container
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]