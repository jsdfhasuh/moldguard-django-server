FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS=*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py check

EXPOSE 18080

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_probe_data && gunicorn config.wsgi:application --bind 0.0.0.0:18080 --workers 1 --threads 4"]
