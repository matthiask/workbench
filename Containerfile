FROM --platform=linux/amd64 python:3.11 as backend
WORKDIR /src
ENV PYTHONUNBUFFERED 1
ADD requirements.txt .
RUN python -m venv venv && venv/bin/pip install -U pip && venv/bin/pip install -r requirements.txt
ADD . /src
COPY conf/_env .env
RUN venv/bin/python manage.py collectstatic --noinput && rm .env
RUN venv/bin/python -m whitenoise.compress static
RUN useradd -U -d /src deploy
USER deploy
EXPOSE 8000
CMD ["venv/bin/python", "-m", "gunicorn", "wsgi:application", "-w", "2", "--bind", "0.0.0.0:8000"]
