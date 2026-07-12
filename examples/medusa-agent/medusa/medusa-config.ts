import { defineConfig, loadEnv } from "@medusajs/framework/utils"

loadEnv(process.env.NODE_ENV || "production", process.cwd())

function requiredEnv(name: string): string {
  const value = process.env[name]
  if (!value) {
    throw new Error(`${name} is required`)
  }
  return value
}

module.exports = defineConfig({
  projectConfig: {
    databaseUrl: requiredEnv("DATABASE_URL"),
    redisUrl: requiredEnv("REDIS_URL"),
    databaseDriverOptions: {
      ssl: false,
      sslmode: "disable",
    },
    http: {
      storeCors: requiredEnv("STORE_CORS"),
      adminCors: requiredEnv("ADMIN_CORS"),
      authCors: requiredEnv("AUTH_CORS"),
      jwtSecret: requiredEnv("JWT_SECRET"),
      cookieSecret: requiredEnv("COOKIE_SECRET"),
    },
  },
  modules: [
    {
      resolve: "@medusajs/medusa/translation",
    },
  ],
  admin: {
    disable: process.env.MEDUSA_DISABLE_ADMIN === "true",
    vite: () => ({
      server: {
        host: "0.0.0.0",
        allowedHosts: ["localhost", ".localhost", "127.0.0.1"],
        hmr: {
          port: 5173,
          clientPort: 5174,
        },
      },
    }),
  },
})

