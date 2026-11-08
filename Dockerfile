# 審査員向けの公開版（docs/DEPLOY.md）。手元で使うときは要らない（README の「動かし方」）
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN pip install --no-cache-dir "uv>=0.11"
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
# 知識ベース（正規版・非公開）は使わない β 版。作業・相談の保存先は消えないディスク（公開先で /var/data に付ける）
ENV KIYAKU_KB_OFF=1 KIYAKU_DATA_DIR=/var/data
EXPOSE 8000
CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
