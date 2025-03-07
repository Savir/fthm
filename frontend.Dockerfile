FROM node:22


# Install dependencies separately to leverage Docker caching
WORKDIR /frontend
COPY ./frontend/package.json ./frontend/package-lock.json ./
RUN npm install --silent