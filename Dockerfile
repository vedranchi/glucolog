# stage 1: base build stage
FROM python:3.13-slim AS builder

# create app directory
RUN mkdir /app

# set the working directory inside the container
WORKDIR /app

# set environment variables to optimize python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# upgrade pip and install dependencies
RUN pip install --upgrade pip

# copy the requirements file first (better caching)
COPY requirements.txt /app/

# install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# stage 2: production stage
FROM python:3.13-slim

RUN useradd -m -r appuser && \
  mkdir /app && \
  chown -R appuser /app


# copy the python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# set the working directory
WORKDIR /app

# copy application code
COPY --chown=appuser:appuser . .

# set environment variables to optimize python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# pre-create the dirs mounted as named volumes in production, owned by appuser,
# so the volumes inherit writable ownership (collectstatic output + media uploads)
RUN mkdir -p /app/staticfiles /app/media && \
  chown -R appuser:appuser /app/staticfiles /app/media


# switch to non root user
USER appuser


# expose the django port
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 60 --graceful-timeout 30 --access-logfile - --error-logfile - core.wsgi:application"]



