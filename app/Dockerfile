FROM node:22-alpine AS build

WORKDIR /workspace

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY app/package.json app/package.json

RUN pnpm install --filter @rag.computer/app --frozen-lockfile

COPY app app

RUN pnpm --filter @rag.computer/app build

FROM nginx:1.29-alpine AS runtime

ENV RAG_COMPUTER_URL=http://localhost:4000

COPY app/nginx.conf /etc/nginx/conf.d/default.conf
COPY app/docker-entrypoint.sh /docker-entrypoint.d/40-rag-computer-config.sh
COPY --from=build /workspace/app/dist /usr/share/nginx/html

RUN chmod +x /docker-entrypoint.d/40-rag-computer-config.sh

EXPOSE 3000
