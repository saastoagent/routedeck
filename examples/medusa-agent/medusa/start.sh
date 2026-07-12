#!/bin/sh
set -eu

APP_MODE="${MEDUSA_APP_MODE:-production}"
SEED_ON_START="${MEDUSA_SEED_ON_START:-0}"

cd /server

for name in DATABASE_URL REDIS_URL JWT_SECRET COOKIE_SECRET STORE_CORS ADMIN_CORS AUTH_CORS; do
  value="$(printenv "$name" 2>/dev/null || true)"
  if [ -z "$value" ]; then
    echo "$name is required" >&2
    exit 78
  fi
done

echo "Running database migrations..."
npm run medusa -- db:migrate

if [ "$SEED_ON_START" = "1" ]; then
  echo "Seeding database..."
  npm run seed
elif [ "$SEED_ON_START" != "0" ]; then
  echo "MEDUSA_SEED_ON_START must be 0 or 1" >&2
  exit 64
else
  echo "Skipping seed; protected demo provisioning owns the canonical seed."
fi

if [ "$APP_MODE" = "development" ]; then
  echo "Starting Medusa development server..."
  exec npm run dev
fi

if [ "$APP_MODE" != "production" ]; then
  echo "MEDUSA_APP_MODE must be development or production" >&2
  exit 65
fi

if [ ! -f "/server/.medusa/server/public/admin/index.html" ]; then
  echo "Build artifacts missing, running one-time production build..."
  npm run build
fi

echo "Starting Medusa production server..."
exec npm run start
