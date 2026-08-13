FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS=*

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc pkg-config default-libmysqlclient-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN python manage.py check \
    && groupadd --system moldguard \
    && useradd --system --gid moldguard --home-dir /app --shell /usr/sbin/nologin moldguard \
    && chown -R moldguard:moldguard /app

USER moldguard

EXPOSE 18080

CMD ["sh", "/app/scripts/container_entrypoint.sh"]
