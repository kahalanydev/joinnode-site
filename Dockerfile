FROM nginx:1.27-alpine

# nginx.conf has to be inside the build context to be copied, so it lands in
# the web root with everything else and is then moved out of it.
COPY . /usr/share/nginx/html
RUN mv /usr/share/nginx/html/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health >/dev/null 2>&1 || exit 1
