FROM python:3.12-slim

WORKDIR /app

# Avoid noisy pyc files + ensure logs flush
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# App Runner provides PORT as a reserved env var (you don't set it yourself).
# Streamlit must bind to 0.0.0.0 and listen on that port.
EXPOSE 8080
CMD ["sh", "-c", "streamlit run dashboard.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true"]