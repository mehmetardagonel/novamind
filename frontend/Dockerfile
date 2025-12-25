# Frontend Dockerfile (Vue 3 + Vite)
# Multi-stage build için

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Package dosyalarını kopyala
COPY package*.json ./

# Bağımlılıkları yükle
RUN npm ci

# Frontend kodunu kopyala
COPY .env .env

COPY . .

# Production build
RUN npm run build

# Stage 2: Production (Nginx ile serve)
FROM nginx:alpine

# Build edilen dosyaları nginx'e kopyala
COPY --from=builder /app/dist /usr/share/nginx/html

# Özel nginx yapılandırması (Vue router için)
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    # HTML dosyaları cache'lenmesin (her zaman fresh) \
    location ~ \.html$ { \
        add_header Cache-Control "no-cache, no-store, must-revalidate"; \
        add_header Pragma "no-cache"; \
        add_header Expires "0"; \
        try_files $uri /index.html; \
    } \
    \
    # Assets (JS/CSS/images) cache'lensin (hash var) \
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ { \
        add_header Cache-Control "public, max-age=31536000, immutable"; \
    } \
    \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    \
    location /api { \
        proxy_pass http://backend:8001; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
    } \
}' > /etc/nginx/conf.d/default.conf

# Port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# Nginx başlat
CMD ["nginx", "-g", "daemon off;"]
