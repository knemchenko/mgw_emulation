FROM python:3.11-slim
WORKDIR /app
COPY services/proto-gen/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/proto-gen/app ./app
COPY services/common ./common
CMD ["python", "-m", "app.main"]
