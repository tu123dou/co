# 后端运行镜像：安装锁定依赖，复制 API 与迁移代码并启动 FastAPI。
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv/backend
WORKDIR /srv
COPY backend/requirements.lock backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock
RUN useradd --create-home appuser
COPY backend backend
COPY scripts/grant-query.py scripts/grant-query.py
USER appuser
# API 启动不依赖外部向量服务；需要重建索引时单独执行 python -m app.retrieval sync。
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && python scripts/grant-query.py && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
