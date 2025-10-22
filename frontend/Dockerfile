################################
# Frontend production image (Nginx)
################################
FROM node:20-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine

# Copy Nginx config and runtime env injector
COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint.sh /docker-entrypoint.d/99-env-inject.sh
RUN chmod +x /docker-entrypoint.d/99-env-inject.sh

# Serve build output
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Runtime-configurable API base URL (injected into index.html)
ENV API_BASE_URL=""

CMD ["nginx", "-g", "daemon off;"]