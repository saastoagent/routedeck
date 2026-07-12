#!/bin/sh
set -eu

corepack enable
corepack prepare pnpm@11.7.0 --activate
pnpm --filter @routedeck/medusa-agent... install \
  --frozen-lockfile \
  --force \
  --node-linker=hoisted
pnpm --filter @routedeck/core build
pnpm --filter @routedeck/react build
exec pnpm --filter @routedeck/medusa-agent exec vite --host 0.0.0.0 --port 5198
