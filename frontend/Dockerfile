FROM node:18-alpine

WORKDIR /app

ARG NODE_ENV=development
ENV NODE_ENV=$NODE_ENV

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

RUN if [ "$NODE_ENV" = "production" ]; then npm run build; fi

EXPOSE 3000

# CMD se nastaví v docker-compose.yml