# -------------------
# Development stage
# -------------------
FROM node:20-alpine AS development
WORKDIR /app

COPY package*.json vite.config.ts tsconfig.json ./
RUN npm install

EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host"]

# -------------------
# Production build stage
# -------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json vite.config.ts tsconfig.json ./
RUN npm install
COPY . .
RUN npm run build

# -------------------
# Production serve stage
# -------------------
FROM nginx:alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
