# Used by docker-compose for local parity with the full stack. On Render,
# the frontend is deployed as a native Static Site instead (see render.yaml)
# — Render builds and serves the `dist/` output directly, no Docker or
# nginx needed there. This Dockerfile exists for docker-compose only.

FROM node:20-slim AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# Vite bakes VITE_* vars into the build at build time, not at container
# start time — so this has to be a build ARG, not just an env var passed
# to `docker run`.
ARG VITE_API_BASE_URL=http://localhost:8000/api/auth
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
