FROM python:3.11

# Nastavení časové zóny pro logování
RUN apt-get update && \
   apt-get install -y tzdata && \
   ln -fs /usr/share/zoneinfo/Europe/Prague /etc/localtime && \
   dpkg-reconfigure --frontend noninteractive tzdata

WORKDIR /app

# Instalace netcat pro kontrolu připojení k databázi
RUN apt-get install -y netcat-traditional

# Instalace závislostí
COPY requirements.txt .
RUN pip install -r requirements.txt

# Kopírování kódu aplikace
COPY . .

# Spuštění aplikace s čekáním na databázi
CMD bash -c '\
   while ! nc -z db 5432; do \
       echo "Waiting for database..." && \
       sleep 1; \
   done && \
   echo "Database is up!" && \
   python manage.py makemigrations && \
   python manage.py migrate && \
   python manage.py runserver 0.0.0.0:8000'