# See https://docs.astral.sh/uv/guides/integration/docker/#available-images
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:debian as backend
WORKDIR /src
ENV PYTHONUNBUFFERED 1
ENV UV_PYTHON_INSTALL_DIR=/opt/uv
ADD pyproject.toml uv.lock .
RUN --mount=type=cache,target=/root/.cache/uv uv sync
ADD . /src
COPY conf/_env .env
RUN uv run python manage.py collectstatic --noinput && rm .env
RUN useradd -U -m deploy
USER deploy
EXPOSE 8000
CMD ["uv", "run", "granian", "--interface", "wsgi", "wsgi:application", "--workers", "2", "--host", "0.0.0.0", "--port", "8000", "--respawn-failed-workers", "--static-path-mount", "/src/static/", "--static-path-expires", "720d"]
