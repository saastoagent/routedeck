#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${ROUTEDECK_DEMO_SENTINEL:?ROUTEDECK_DEMO_SENTINEL is required}"
: "${ROUTEDECK_DEMO_GENERATED_MANIFEST:?ROUTEDECK_DEMO_GENERATED_MANIFEST is required}"

cd /server

SETUP_STATE="$(node <<'NODE'
const { Client } = require("pg")

async function main() {
  const client = new Client({ connectionString: process.env.DATABASE_URL })
  await client.connect()
  const sentinelTable = await client.query(
    "SELECT to_regclass('public.routedeck_demo_sentinel') AS table_name"
  )
  if (sentinelTable.rows[0].table_name) {
    const sentinel = await client.query("SELECT count(*) AS count FROM routedeck_demo_sentinel")
    await client.end()
    process.stdout.write(Number(sentinel.rows[0].count) > 0 ? "sentinel" : "partial")
    return
  }
  const tables = await client.query(`
    SELECT to_regclass('public.product') AS product,
           to_regclass('public.product_variant') AS product_variant,
           to_regclass('public.region') AS region,
           to_regclass('public.sales_channel') AS sales_channel,
           to_regclass('public.shipping_option') AS shipping_option,
           to_regclass('public.api_key') AS api_key
  `)
  const tableNames = Object.values(tables.rows[0])
  if (tableNames.every((value) => value === null)) {
    await client.end()
    process.stdout.write("empty")
    return
  }
  if (tableNames.some((value) => value === null)) {
    await client.end()
    process.stdout.write("partial")
    return
  }
  const counts = await client.query(`
    SELECT (SELECT count(*) FROM product) AS products,
           (SELECT count(*) FROM product_variant) AS variants,
           (SELECT count(*) FROM region) AS regions,
           (SELECT count(*) FROM sales_channel) AS sales_channels,
           (SELECT count(*) FROM shipping_option) AS shipping_options,
           (SELECT count(*) FROM api_key WHERE type = 'publishable') AS publishable_keys
  `)
  await client.end()
  const values = Object.values(counts.rows[0]).map(Number)
  if (values.every((value) => value === 0)) {
    process.stdout.write("empty")
    return
  }
  const expected = [4, 20, 1, 1, 2, 1]
  process.stdout.write(
    values.every((value, index) => value === expected[index]) ? "seeded" : "partial"
  )
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
NODE
)"

if [ "$SETUP_STATE" = "sentinel" ]; then
  echo "Protected RouteDeck demo sentinel already exists; refusing to migrate or reseed." >&2
  exit 64
fi
if [ "$SETUP_STATE" = "partial" ]; then
  echo "Protected database contains partial or unexpected data; refusing recovery and reseed." >&2
  exit 65
fi

if [ "$SETUP_STATE" = "empty" ]; then
  echo "Running Medusa migrations for the protected demo database..."
  npm run medusa -- db:migrate --execute-all-links

  echo "Running the deterministic Medusa seed exactly once..."
  npm run seed
else
  echo "Interrupted provision detected with complete canonical seed data."
  echo "Skipping migrations and seed; recovering only manifest and sentinel."
fi

echo "Emitting the allowlisted seed manifest and database sentinel..."
ROUTEDECK_DEMO_SENTINEL_ACTION=provision \
  npm run medusa -- exec /server/src/scripts/routedeck-demo/medusa-sentinel.ts

echo "Protected Medusa demo provisioning completed."
