FROM --platform=linux/amd64 python:3.13-slim as backend
WORKDIR /src
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/usr/local
ADD requirements.txt .
RUN pip install uv && uv pip install -r requirements.txt --system
ADD . /src
COPY conf/_env .env
RUN python manage.py collectstatic --noinput && rm .env
RUN python -m whitenoise.compress static
RUN useradd -U -d /src deploy
USER deploy
EXPOSE 8000
CMD ["granian", "--interface", "wsgi", "wsgi:application", "--workers", "2", "--host", "0.0.0.0", "--port", "8000", "--respawn-failed-workers"]
