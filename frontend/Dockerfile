FROM node:18-alpine

WORKDIR /app

# Nastavení NODE_OPTIONS pro správu paměti
ENV NODE_OPTIONS="--max-old-space-size=2048"

ARG NODE_ENV=development
ENV NODE_ENV=$NODE_ENV

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# První zkopírujeme pouze package.json soubory pro lepší využití cache
COPY package*.json ./
RUN npm install --legacy-peer-deps

# Pak zkopírujeme zbytek aplikace
COPY . .

# Optimalizace pro produkční build
RUN if [ "$NODE_ENV" = "production" ]; then \
    npm run build && \
    npm prune --production; \
    fi

EXPOSE 3000

# CMD se nastaví v docker-compose.yml