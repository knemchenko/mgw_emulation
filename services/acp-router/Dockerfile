FROM python:3.11-slim
WORKDIR /app
COPY services/acp-router/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/acp-router/app ./app
COPY services/common ./common
EXPOSE 8002
CMD ["python", "-m", "app.main"]
