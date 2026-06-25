# A股智能体分析系统 - Docker配置
# 适用于 Render / Railway / Fly.io 等平台

FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（使用国内镜像加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY --chown=appuser:appuser . .

# 创建必要目录
RUN mkdir -p /app/output /app/logs && chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 暴露端口
ENV PORT=8000
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]