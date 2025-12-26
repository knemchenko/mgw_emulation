FROM python:3.11-slim
WORKDIR /app
COPY services/protocol-agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/protocol-agent/app ./app
COPY services/common ./common
CMD ["python", "-m", "app.main"]
