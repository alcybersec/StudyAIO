# Stage 1: Build the React application
FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Vite inlines VITE_* at build time, so Sentry has to be configured here
# rather than in the runtime environment. Empty (the default) disables it.
ARG VITE_SENTRY_DSN=""
ARG VITE_SENTRY_ENVIRONMENT="production"
ARG VITE_SENTRY_RELEASE=""
ARG VITE_SENTRY_TRACES_SAMPLE_RATE="0"
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN \
    VITE_SENTRY_ENVIRONMENT=$VITE_SENTRY_ENVIRONMENT \
    VITE_SENTRY_RELEASE=$VITE_SENTRY_RELEASE \
    VITE_SENTRY_TRACES_SAMPLE_RATE=$VITE_SENTRY_TRACES_SAMPLE_RATE

RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:1.27-alpine

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Add .mjs MIME type (not in nginx defaults, needed for pdfjs web worker)
RUN sed -i '/application\/javascript/s/;/ mjs;/' /etc/nginx/mime.types

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/studyaio.conf

# OCI image labels
LABEL org.opencontainers.image.source="https://github.com/alcybersec/StudyAIO"
LABEL org.opencontainers.image.description="StudyAIO UI (nginx + React)"
LABEL org.opencontainers.image.licenses="MIT"

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
