FROM nginx:stable-alpine

# Копируем кастомную конфигурацию nginx
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf /etc/nginx/conf.d/default.conf

# Создаём простую HTML страницу для тестирования
RUN echo '<!DOCTYPE html><html><head><title>NGINX Test</title></head><body><h1>NGINX is running!</h1></body></html>' > /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
