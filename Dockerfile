FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY data/ ./data/

# 暴露远程 HTTP 通道（默认监听 8765，路径 /mcp）
EXPOSE 8765

ENTRYPOINT ["python", "server.py"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8765", "--stateless"]
