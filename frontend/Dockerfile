FROM node:22-alpine AS build
WORKDIR /src
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build
FROM nginx:1.27-alpine
COPY ops/nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=4s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
