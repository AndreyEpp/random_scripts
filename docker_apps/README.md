# Базовые команды docker and docker-compose

Запуск и просмотр файлов производится из репозитория приложения


### Локально сборка докер / докер compose файла для внутреннего теста. Флаг -d - запуска в фоновом режиме
docker build . -t name:latest 
docker run -d -p 7343:8000 name   (7343 рандомный номер порта, после каждой сборки необходимо менять номер)
docker logs

docker compose build
docker compose up -d 

### На линуксе при наличий compose файла

sudo docker-compose build
sudo docker-compose up -d

sudo docker-compose ps    - показать


### Очистка всех неиспользуемых или не связанных с контейнерами образов, контейнеров, томов и сетей
- В Docker имеется команда, очищающая все не связанные с контейнерами ресурсы, в том числе образы, контейнеры, тома и сети:

sudo docker system prune

### Чтобы удалить все остановленные контейнеры и неиспользуемые образы (а не только образы, не связанные с контейнерами), добавьте в эту команду флаг -a:

sudo docker system prune -a

### Еще команды
- https://www.digitalocean.com/community/tutorials/how-to-remove-docker-images-containers-and-volumes-ru
- https://habr.com/ru/companies/flant/articles/336654/
- https://habr.com/ru/companies/first/articles/592321/ Различия между Docker Compose up, up -d, stop, start, down и down -v

### Stop services only
docker-compose stop

### Stop and remove containers, networks..
docker-compose down 

### Down and remove volumes
docker-compose down --volumes 

### Down and remove images
docker-compose down --rmi <all|local> 

курс
https://stepik.org/course/74010/