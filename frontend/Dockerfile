FROM node:18-alpine

WORKDIR /app

# Přidáme ARG pro build-time proměnnou
ARG NEXT_PUBLIC_API_URL=http://localhost:8000

# Nastavíme ji jako ENV
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]