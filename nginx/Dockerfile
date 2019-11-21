FROM nginx:1.17.5

RUN rm /etc/nginx/nginx.conf
COPY nginx.conf /etc/nginx
RUN rm /etc/nginx/conf.d/default.conf
COPY financial.conf /etc/nginx/conf.d/
