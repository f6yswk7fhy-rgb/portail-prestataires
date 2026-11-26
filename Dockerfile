FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN useradd --system --uid 10001 --home /app portail
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=portail:portail . .
RUN PORTAIL_DEBUG=1 python manage.py collectstatic --noinput

USER portail
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn portail.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]
