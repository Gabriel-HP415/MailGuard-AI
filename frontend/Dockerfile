# Multi-stage build:
# 1) Pull vendored CSS/JS via Python (handles corporate proxies)
# 2) Serve via nginx:alpine (tiny image)

FROM python:3.11-alpine AS fetcher

WORKDIR /work
COPY scripts/fetch_frontend_assets.py /work/fetch_frontend_assets.py

# Mirror the script's expected layout so its writes land in /work/frontend/assets
RUN mkdir -p /work/frontend/assets/css /work/frontend/assets/vendor
RUN python /work/fetch_frontend_assets.py

FROM nginx:1.27-alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/Dockerfile.nginx /etc/nginx/conf.d/mailguard.conf

# Copy site
COPY frontend/ /usr/share/nginx/html/

# Overwrite the assets we just downloaded
COPY --from=fetcher /work/frontend/assets/ /usr/share/nginx/html/assets/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
