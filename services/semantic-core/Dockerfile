FROM python:3.11-slim
WORKDIR /app
COPY services/semantic-core/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/semantic-core/app ./app
COPY services/common ./common
EXPOSE 8003
CMD ["python", "-m", "app.main"]
