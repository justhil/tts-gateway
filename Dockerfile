FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8080
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "httpx>=0.27" \
    "pydantic>=2" \
    "pydantic-settings>=2"
COPY app ./app
COPY static ./static
COPY data ./data
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]