FROM node:22-alpine AS build

WORKDIR /workspace

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY app/package.json app/package.json

RUN pnpm install --filter @bigrag/app --frozen-lockfile

COPY app app

RUN pnpm --filter @bigrag/app build

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=build --chown=nextjs:nodejs /workspace/app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /workspace/app/.next/static ./app/.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "app/server.js"]
