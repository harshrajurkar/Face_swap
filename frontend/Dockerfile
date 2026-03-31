FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY pages ./pages
COPY styles ./styles

RUN npm run build

CMD ["npm", "run", "start"]
