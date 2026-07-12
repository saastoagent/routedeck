FROM node:20.19.4-bookworm-slim@sha256:6db5e436948af8f0244488a1f658c2c8e55a3ae51ca2e1686ed042be8f25f70a

WORKDIR /server

ENV NODE_ENV=development

COPY package.json package-lock.json tsconfig.json medusa-config.ts ./
COPY src ./src
COPY start.sh ./start.sh

RUN npm ci --no-audit --no-fund \
  && chmod +x ./start.sh

EXPOSE 9000 5173

CMD ["./start.sh"]

