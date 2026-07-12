import { writeFileSync } from "node:fs"

import { ExecArgs } from "@medusajs/framework/types"
import { ContainerRegistrationKeys } from "@medusajs/framework/utils"

import {
  canonicalizeSeedData,
  SeedBusinessData,
  SeedFingerprintContract,
} from "./seed-fingerprint"

const { Client } = require("pg")
const contract = require("./demo-manifest.json") as SeedFingerprintContract

export default async function maintainDemoSentinel({ container }: ExecArgs) {
  const action = process.env.ROUTEDECK_DEMO_SENTINEL_ACTION
  if (action !== "provision" && action !== "validate") {
    throw new Error("ROUTEDECK_DEMO_SENTINEL_ACTION must be provision or validate")
  }
  if (process.env.ROUTEDECK_DEMO_SENTINEL !== contract.sentinel) {
    throw new Error("runtime sentinel does not match demo-manifest.json")
  }
  const databaseUrl = requireEnvironment("DATABASE_URL")
  const generatedPath = requireEnvironment("ROUTEDECK_DEMO_GENERATED_MANIFEST")
  const query = container.resolve(ContainerRegistrationKeys.QUERY)

  const [{ data: products }, { data: regions }, { data: salesChannels }, { data: shippingOptions }] =
    await Promise.all([
      query.graph({
        entity: "product",
        fields: ["handle", "title", "status", "variants.sku", "variants.title"],
      }),
      query.graph({
        entity: "region",
        fields: ["id", "name", "currency_code", "countries.iso_2", "payment_providers.id"],
      }),
      query.graph({ entity: "sales_channel", fields: ["id", "name"] }),
      query.graph({
        entity: "shipping_option",
        fields: ["name", "price_type", "provider_id", "type.code"],
      }),
    ])

  const productRows = (products ?? []) as Array<Record<string, any>>
  const regionRows = (regions ?? []) as Array<Record<string, any>>
  const salesChannelRows = (salesChannels ?? []) as Array<Record<string, any>>
  const shippingOptionRows = (shippingOptions ?? []) as Array<Record<string, any>>
  const paymentProviderIds = new Set<string>()
  for (const region of regionRows) {
    for (const provider of region.payment_providers ?? []) {
      paymentProviderIds.add(provider.id)
    }
  }

  const data: SeedBusinessData = {
    products: productRows.map((product) => ({
      handle: product.handle,
      title: product.title,
      status: product.status,
    })),
    variants: productRows.flatMap((product) =>
      (product.variants ?? []).map((variant: Record<string, any>) => ({
        product_handle: product.handle,
        sku: variant.sku,
        title: variant.title,
      }))
    ),
    regions: regionRows.map((region) => ({
      name: region.name,
      currency_code: region.currency_code,
      country_codes: (region.countries ?? []).map(
        (country: Record<string, any>) => country.iso_2
      ),
    })),
    sales_channels: salesChannelRows.map((channel) => ({ name: channel.name })),
    shipping_options: shippingOptionRows.map((option) => ({
      name: option.name,
      price_type: option.price_type,
      provider_id: option.provider_id,
      type_code: option.type?.code,
    })),
    enabled_payment_providers: [...paymentProviderIds].map((id) => ({ id })),
  }

  const manifest = canonicalizeSeedData(contract, data)
  writeFileSync(generatedPath, `${JSON.stringify(manifest, null, 2)}\n`, {
    encoding: "utf8",
    flag: "w",
  })

  const client = new Client({ connectionString: databaseUrl })
  await client.connect()
  try {
    const publishableKeys = await client.query(
      "SELECT token FROM api_key WHERE type = 'publishable' AND deleted_at IS NULL ORDER BY created_at"
    )
    const selectedRegions = regionRows.filter((region) => region.name === "Europe")
    const selectedChannels = salesChannelRows.filter(
      (channel) => channel.name === "Default Sales Channel"
    )
    if (publishableKeys.rowCount !== 1) {
      throw new Error("expected exactly one enabled publishable API key")
    }
    if (selectedRegions.length !== 1 || !selectedRegions[0].id) {
      throw new Error("expected exactly one Europe region with a generated ID")
    }
    const selectedCountryCodes = new Set(
      (selectedRegions[0].countries ?? []).map(
        (country: Record<string, any>) => country.iso_2
      )
    )
    if (!selectedCountryCodes.has("gb")) {
      throw new Error("expected the Europe region to contain configured buyer country gb")
    }
    if (selectedChannels.length !== 1 || !selectedChannels[0].id) {
      throw new Error("expected exactly one Default Sales Channel with a generated ID")
    }
    if (paymentProviderIds.size !== 1 || !paymentProviderIds.has("pp_system_default")) {
      throw new Error("expected exactly the pp_system_default payment provider")
    }
    writeFileSync(
      "/demo/CREDS.generated.env",
      [
        `MEDUSA_PUBLISHABLE_KEY=${publishableKeys.rows[0].token}`,
        `MEDUSA_REGION_ID=${selectedRegions[0].id}`,
        "MEDUSA_COUNTRY_CODE=gb",
        `MEDUSA_SALES_CHANNEL_ID=${selectedChannels[0].id}`,
        "MEDUSA_PAYMENT_PROVIDER_ID=pp_system_default",
        "",
      ].join("\n"),
      { encoding: "utf8", flag: "w" }
    )
    await client.query("BEGIN")
    await client.query(`
      CREATE TABLE IF NOT EXISTS routedeck_demo_sentinel (
        sentinel_id text PRIMARY KEY,
        contract_version integer NOT NULL,
        manifest_sha256 text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    `)
    const existing = await client.query(
      "SELECT sentinel_id, contract_version, manifest_sha256 FROM routedeck_demo_sentinel"
    )
    if (action === "provision") {
      if (existing.rowCount !== 0) {
        throw new Error("protected database sentinel already exists; refusing reseed")
      }
      await client.query(
        "INSERT INTO routedeck_demo_sentinel(sentinel_id, contract_version, manifest_sha256) VALUES ($1, $2, $3)",
        [manifest.sentinel, manifest.contract_version, manifest.sha256]
      )
    } else {
      if (
        existing.rowCount !== 1 ||
        existing.rows[0].sentinel_id !== manifest.sentinel ||
        existing.rows[0].contract_version !== manifest.contract_version ||
        existing.rows[0].manifest_sha256 !== manifest.sha256
      ) {
        throw new Error("protected database sentinel or seed fingerprint mismatch")
      }
    }
    await client.query("COMMIT")
  } catch (error) {
    await client.query("ROLLBACK")
    throw error
  } finally {
    await client.end()
  }
}

function requireEnvironment(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`${name} is required`)
  }
  return value
}
