FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY pages ./pages

CMD ["npm", "run", "dev"]
