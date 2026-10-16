# Production image: Vite build served as static files by Nginx.
# Local development keeps using Dockerfile.dev (Vite HMR server).
# The app calls the API via the relative default '/api/v1' (see
# src/api/client.ts), which Nginx proxies to the backend below, so no
# build-time API URL is required.
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
