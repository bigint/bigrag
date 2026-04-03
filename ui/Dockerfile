FROM node:22-alpine AS build

RUN corepack enable && corepack prepare pnpm@latest --activate

# Build TypeScript SDK (UI depends on it)
WORKDIR /sdks/typescript
COPY sdks/typescript/ .
RUN pnpm install && pnpm build

# Install UI dependencies
WORKDIR /app
COPY ui/package.json ui/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

# Build UI
COPY ui/ .
RUN pnpm build

FROM node:22-alpine

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 5000

ENV PORT=5000
ENV HOSTNAME=0.0.0.0

CMD ["node", "server.js"]
