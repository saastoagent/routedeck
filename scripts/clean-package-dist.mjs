import { rmSync } from "node:fs";
import { basename, resolve } from "node:path";

const packageRoot = process.cwd();
const packageName = basename(packageRoot);
const allowedPackages = new Set(["core", "react", "testing"]);

if (!allowedPackages.has(packageName) || basename(resolve(packageRoot, "..")) !== "packages") {
  throw new Error(`Refusing to clean dist from unexpected directory: ${packageRoot}`);
}

rmSync(resolve(packageRoot, "dist"), { recursive: true, force: true });
rmSync(resolve(packageRoot, "..", "..", ".cache", "typescript", `${packageName}.tsbuildinfo`), {
  force: true,
});
