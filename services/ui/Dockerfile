# Stage 1: Build the React application
FROM node:20-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0 AS build

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

# Stage 2: Serve with unprivileged nginx (listens on 3000, pid and temp files
# under /tmp, so the container also runs with a read-only root filesystem).
FROM nginxinc/nginx-unprivileged:1.30.6-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# Config edits need root; the image's unprivileged user is restored below.
USER root

# Even the current upstream tag lags Alpine's security fixes. Upgrading here
# keeps the image scan clean; the digest pin still fixes WHICH base is
# upgraded, and Renovate moves it.
RUN apk upgrade --no-cache

# Remove default nginx config (it listens on 8080)
RUN rm /etc/nginx/conf.d/default.conf

# Add .mjs MIME type (not in nginx defaults, needed for pdfjs web worker)
RUN sed -i '/application\/javascript/s/;/ mjs;/' /etc/nginx/mime.types

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/studyaio.conf

# OCI image labels
LABEL org.opencontainers.image.source="https://github.com/alcybersec/StudyAIO"
LABEL org.opencontainers.image.description="StudyAIO UI (nginx + React)"
LABEL org.opencontainers.image.licenses="MIT"

# Copy built assets from build stage (root-owned, read-only to nginx)
COPY --from=build /app/dist /usr/share/nginx/html

USER 101

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
