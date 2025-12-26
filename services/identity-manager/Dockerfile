FROM python:3.11-slim
WORKDIR /app
COPY services/identity-manager/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/identity-manager/app ./app
COPY services/common ./common
EXPOSE 8001
CMD ["python", "-m", "app.main"]
