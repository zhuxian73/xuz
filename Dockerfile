# 使用官方 Python 运行时作为父镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# 禁用字节码生成
ENV PYTHONDONTWRITEBYTECODE=1
# 禁用缓冲以实时查看日志
ENV PYTHONUNBUFFERED=1
# 设置 Gradio 监听所有接口
ENV GRADIO_SERVER_NAME="0.0.0.0"
# 设置 Gradio 端口
ENV GRADIO_SERVER_PORT=8715

# 安装系统依赖（如果需要执行 shell 命令，可能需要一些基础工具）
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY src/ ./src/
COPY .env* ./

# 暴露 Gradio 默认端口
EXPOSE 8715

# 启动命令
CMD ["python", "-m", "src.agent", "--gui"]
