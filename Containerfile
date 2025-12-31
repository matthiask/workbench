# See https://docs.astral.sh/uv/guides/integration/docker/#available-images
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.14-trixie as backend
WORKDIR /src
ENV PYTHONUNBUFFERED 1
ADD requirements.txt .
RUN uv venv && uv pip install -r requirements.txt
ADD . /src
COPY conf/_env .env
RUN uv run python manage.py collectstatic --noinput && rm .env
RUN useradd -U -m deploy
USER deploy
EXPOSE 8000
CMD ["uv", "run", "granian", "--interface", "wsgi", "wsgi:application", "--workers", "2", "--host", "0.0.0.0", "--port", "8000", "--respawn-failed-workers", "--static-path-mount", "/src/static/", "--static-path-expires", "720d"]
