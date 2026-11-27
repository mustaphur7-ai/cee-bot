FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md requirements.txt ./
COPY cli ./cli
COPY tradingagents ./tradingagents
RUN pip install --no-cache-dir .
CMD ["cee-bot", "watch"]
