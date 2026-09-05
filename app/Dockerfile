FROM node:24-alpine AS build

WORKDIR /workspace

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY app/package.json app/package.json
COPY sdks/typescript/package.json sdks/typescript/package.json

RUN pnpm install --filter @bigrag/app... --frozen-lockfile

COPY app app
COPY sdks/typescript sdks/typescript

RUN pnpm --filter @bigrag/client build
RUN pnpm --filter @bigrag/app build

FROM nginx:1.31-alpine AS runtime

COPY app/nginx.conf /etc/nginx/conf.d/default.conf
COPY app/docker-entrypoint.sh /docker-entrypoint.d/40-bigrag-config.sh
COPY --from=build /workspace/app/dist /usr/share/nginx/html

RUN chmod +x /docker-entrypoint.d/40-bigrag-config.sh

EXPOSE 3000
