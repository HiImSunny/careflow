FROM node:20-alpine

WORKDIR /app

# Install dependencies first (layer caching)
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the frontend source
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
