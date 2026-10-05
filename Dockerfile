# Образ для разработки и запуска: Python 3.11 + uv, зависимости строго по uv.lock.
# Сборка:  docker build -t ecg-ptbxl .
# Запуск:  docker run --rm -it -v "$PWD:/app" ecg-ptbxl
# Подробнее: docs/setup.md, раздел "Docker".
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Зависимости отдельным слоем: пересобирается только при изменении uv.lock
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

# Код проекта
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

EXPOSE 8888
CMD ["bash"]
