FROM node:18-alpine

WORKDIR /app

ENV NODE_OPTIONS="--max-old-space-size=2048"

ARG NODE_ENV=development
ENV NODE_ENV=$NODE_ENV

ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

# Vždy provedeme build, bez ohledu na NODE_ENV
RUN npm run build

EXPOSE 3000

# Defaultní command pro spuštění zkompilované aplikace
CMD ["npm", "start"]