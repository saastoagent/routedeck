import { createHash } from "node:crypto"

export const COLLECTION_NAMES = [
  "products",
  "variants",
  "regions",
  "sales_channels",
  "shipping_options",
  "enabled_payment_providers",
] as const

type CollectionName = (typeof COLLECTION_NAMES)[number]
type StableValue = string | number | boolean | string[]
type StableRecord = Record<string, StableValue>

export type SeedFingerprintContract = {
  contract_version: number
  sentinel: string
  collections: Record<
    CollectionName,
    { fields: string[]; sort_by: string[]; expected_keys: string[] }
  >
  excluded_fields: string[]
  excluded_collections: string[]
}

export type SeedBusinessData = Record<CollectionName, StableRecord[]>

export type CanonicalSeedManifest = {
  contract_version: number
  sentinel: string
  sha256: string
  data: SeedBusinessData
}

const TOP_LEVEL_KEYS = [
  "collections",
  "contract_version",
  "excluded_collections",
  "excluded_fields",
  "sentinel",
]
const COLLECTION_RULE_KEYS = ["expected_keys", "fields", "sort_by"]
const REQUIRED_EXCLUDED_FIELDS = [
  "created_at",
  "deleted_at",
  "id",
  "metadata",
  "updated_at",
]
const REQUIRED_EXCLUDED_COLLECTIONS = ["carts", "orders"]

export function canonicalizeSeedData(
  rawContract: unknown,
  rawData: unknown
): CanonicalSeedManifest {
  const contract = validateContract(rawContract)
  const dataObject = requireObject(rawData, "seed business data")
  assertExactKeys(dataObject, [...COLLECTION_NAMES], "seed business data")

  const canonicalData = {} as SeedBusinessData
  for (const collectionName of COLLECTION_NAMES) {
    const rule = contract.collections[collectionName]
    const rawRows = dataObject[collectionName]
    if (!Array.isArray(rawRows) || rawRows.length === 0) {
      throw new Error(`${collectionName} must be a non-empty array`)
    }
    const rows = rawRows.map((rawRow, index) => {
      const row = requireObject(rawRow, `${collectionName}[${index}]`)
      assertExactKeys(row, rule.fields, `${collectionName}[${index}]`)
      const canonicalRow: StableRecord = {}
      for (const field of rule.fields) {
        canonicalRow[field] = validateStableValue(
          row[field],
          `${collectionName}[${index}].${field}`
        )
      }
      return canonicalRow
    })
    canonicalData[collectionName] = [...rows].sort((left, right) =>
      compareRows(left, right, rule.sort_by)
    )
    const actualKeys = canonicalData[collectionName].map((row) =>
      rule.sort_by.map((field) => String(row[field])).join("::")
    )
    if (JSON.stringify(actualKeys) !== JSON.stringify(rule.expected_keys)) {
      throw new Error(
        `${collectionName} business keys do not match the protected seed contract`
      )
    }
  }

  const fingerprintInput = {
    contract_version: contract.contract_version,
    sentinel: contract.sentinel,
    data: canonicalData,
  }
  const canonicalJson = JSON.stringify(fingerprintInput)
  return {
    ...fingerprintInput,
    sha256: createHash("sha256").update(canonicalJson, "utf8").digest("hex"),
  }
}

function validateContract(rawContract: unknown): SeedFingerprintContract {
  const contract = requireObject(rawContract, "seed fingerprint contract")
  assertExactKeys(contract, TOP_LEVEL_KEYS, "seed fingerprint contract")
  if (!Number.isInteger(contract.contract_version) || contract.contract_version !== 1) {
    throw new Error("contract_version must be exactly 1")
  }
  if (contract.sentinel !== "routedeck-medusa-demo-v1") {
    throw new Error("manifest sentinel does not identify the protected demo stack")
  }
  const collections = requireObject(contract.collections, "collections")
  assertExactKeys(collections, [...COLLECTION_NAMES], "collections")
  const validatedCollections = {} as SeedFingerprintContract["collections"]
  for (const collectionName of COLLECTION_NAMES) {
    const rule = requireObject(collections[collectionName], collectionName)
    assertExactKeys(rule, COLLECTION_RULE_KEYS, collectionName)
    const fields = validateUniqueStrings(rule.fields, `${collectionName}.fields`)
    const sortBy = validateUniqueStrings(rule.sort_by, `${collectionName}.sort_by`)
    const expectedKeys = validateUniqueStrings(
      rule.expected_keys,
      `${collectionName}.expected_keys`
    )
    if (sortBy.some((field) => !fields.includes(field))) {
      throw new Error(`${collectionName}.sort_by must reference allowlisted fields`)
    }
    validatedCollections[collectionName] = {
      fields,
      sort_by: sortBy,
      expected_keys: expectedKeys,
    }
  }
  const excludedFields = validateUniqueStrings(
    contract.excluded_fields,
    "excluded_fields"
  )
  const excludedCollections = validateUniqueStrings(
    contract.excluded_collections,
    "excluded_collections"
  )
  assertSameMembers(
    excludedFields,
    REQUIRED_EXCLUDED_FIELDS,
    "excluded_fields"
  )
  assertSameMembers(
    excludedCollections,
    REQUIRED_EXCLUDED_COLLECTIONS,
    "excluded_collections"
  )
  return {
    contract_version: 1,
    sentinel: "routedeck-medusa-demo-v1",
    collections: validatedCollections,
    excluded_fields: excludedFields,
    excluded_collections: excludedCollections,
  }
}

function requireObject(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`)
  }
  return value as Record<string, unknown>
}

function assertExactKeys(
  value: Record<string, unknown>,
  expected: string[],
  label: string
): void {
  const actual = Object.keys(value).sort()
  const wanted = [...expected].sort()
  if (JSON.stringify(actual) !== JSON.stringify(wanted)) {
    throw new Error(
      `${label} fields must be exact; expected=${wanted.join(",")} actual=${actual.join(",")}`
    )
  }
}

function validateUniqueStrings(value: unknown, label: string): string[] {
  if (
    !Array.isArray(value) ||
    value.length === 0 ||
    value.some((item) => typeof item !== "string" || item.length === 0) ||
    new Set(value).size !== value.length
  ) {
    throw new Error(`${label} must be a non-empty unique string array`)
  }
  return [...value]
}

function validateStableValue(value: unknown, label: string): StableValue {
  if (["string", "number", "boolean"].includes(typeof value)) {
    return value as string | number | boolean
  }
  if (
    Array.isArray(value) &&
    value.every((item) => typeof item === "string")
  ) {
    return [...value].sort()
  }
  throw new Error(`${label} must contain only stable scalar data or string arrays`)
}

function compareRows(
  left: StableRecord,
  right: StableRecord,
  sortBy: string[]
): number {
  for (const field of sortBy) {
    const comparison = JSON.stringify(left[field]).localeCompare(
      JSON.stringify(right[field]),
      "en"
    )
    if (comparison !== 0) {
      return comparison
    }
  }
  return JSON.stringify(left).localeCompare(JSON.stringify(right), "en")
}

function assertSameMembers(
  actual: string[],
  expected: string[],
  label: string
): void {
  if (
    JSON.stringify([...actual].sort()) !== JSON.stringify([...expected].sort())
  ) {
    throw new Error(`${label} does not match the protected exclusion contract`)
  }
}
