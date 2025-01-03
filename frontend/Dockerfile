FROM node:18-alpine

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

# Zkopírování package souborů
COPY package*.json ./
RUN npm install --legacy-peer-deps

# Zkopírování zbytku aplikace
COPY . .

# Nastavení proměnných prostředí
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NODE_ENV
ENV NODE_ENV=$NODE_ENV

ARG NODE_OPTIONS
ENV NODE_OPTIONS=$NODE_OPTIONS

# Build aplikace
RUN npm run build

EXPOSE 3000

# Spuštění produkční verze
CMD ["npm", "start"]