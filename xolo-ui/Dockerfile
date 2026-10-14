FROM node:22-alpine AS build

ARG XOLO_VERSION=development
ENV NUXT_PUBLIC_VERSION=${XOLO_VERSION}
WORKDIR /app

RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runtime
ARG XOLO_VERSION=development
LABEL org.opencontainers.image.title="Xolo UI" \
      org.opencontainers.image.version="${XOLO_VERSION}" \
      org.opencontainers.image.source="https://github.com/nachocode/xolo"
ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000 \
    NUXT_PUBLIC_VERSION=${XOLO_VERSION}
WORKDIR /app
COPY --from=build /app/.output ./.output
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
