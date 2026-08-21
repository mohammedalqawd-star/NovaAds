FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY hamelha_ai/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY hamelha_ai /app/hamelha_ai
RUN mkdir -p /app/data/work
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","hamelha_ai.bot"]
