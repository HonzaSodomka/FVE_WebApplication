FROM python:3.11

WORKDIR /app

# Instalace netcat pro kontrolu databáze
RUN apt-get update && apt-get install -y netcat-traditional

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Přidání skriptu pro čekání na databázi a spouštění migrací
CMD bash -c '\
    while ! nc -z db 5432; do \
        echo "Waiting for database..." && \
        sleep 1; \
    done && \
    echo "Database is up!" && \
    python manage.py makemigrations && \
    python manage.py migrate && \
    python manage.py runserver 0.0.0.0:8000'