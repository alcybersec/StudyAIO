# Stage 1: Build the React application
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Add .mjs MIME type (not in nginx defaults, needed for pdfjs web worker)
RUN sed -i '/application\/javascript/s/;/ mjs;/' /etc/nginx/mime.types

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/studyaio.conf

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
