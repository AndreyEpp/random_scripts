### API patient's address. Рабочая версия
Проект состоит:
а) само приложение принимающее и обрабатывающее запрос (main, district_service)
    - файл app.config содержит настройку сервера на котором будет работать сервис (порты, видимость актуального IP)
б) база данных содержащая информацию по адресам и районам (mysql/mysql_connect)
    - файл root содержит сертификат подключения к яндексу
в) Nginx — веб-сервер, HTTP-сервер и обратный прокси-сервер

## todo
- поменять протокол передачи http => на https!!!!!!!!!!!!!!!!!!

Создание 15/01/2024
Автор Андрей Эпп

# Базовые команды

### Для сборки контейнера и запуска в фоновом режиме На линуксе compose файл (PROD)

sudo docker-compose build
sudo docker-compose up -d

sudo docker-compose ps    - показать состояние запущенных контейнеров

### Stop services only
docker-compose stop

### Stop and remove containers, networks..
docker-compose down 

### Down and remove volumes
docker-compose down --volumes 

### Down and remove images
docker-compose down --rmi <all|local> 


### Локально сборка докер / докер compose файла для внутреннего теста. Флаг -d - запуска в фоновом режиме
docker build . -t name:latest 
docker run -d -p 7343:8000 name   (7343 рандомный номер порта, после каждой сборки необходимо менять номер)
docker logs

docker compose build
docker compose up -d 