import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import nextEnv from "@next/env";

const { loadEnvConfig } = nextEnv;

const mode = process.argv[2] ?? "update";
if (!["update", "check"].includes(mode)) {
  throw new Error("Usage: node scripts/api-types.mjs <update|check>");
}

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectDirectory = resolve(scriptDirectory, "..");
const generatedPath = join(projectDirectory, "src", "lib", "api", "generated.ts");
loadEnvConfig(projectDirectory);

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/+$/,
  "",
);
const openApiUrl = process.env.OPENAPI_URL ?? `${apiBaseUrl}/openapi.json`;
const timeoutText = process.env.OPENAPI_TIMEOUT_MS ?? "15000";
if (!/^\d+$/.test(timeoutText)) {
  throw new Error("OPENAPI_TIMEOUT_MS must be a positive whole number");
}
const timeoutMs = Number(timeoutText);
if (timeoutMs < 1_000 || timeoutMs > 120_000) {
  throw new Error("OPENAPI_TIMEOUT_MS must be between 1000 and 120000");
}

const temporaryDirectory = mkdtempSync(join(tmpdir(), "gamelens-openapi-"));
const schemaPath = join(temporaryDirectory, "openapi.json");
const candidatePath = join(temporaryDirectory, "generated.ts");
const cliPath = join(
  projectDirectory,
  "node_modules",
  "openapi-typescript",
  "bin",
  "cli.js",
);

try {
  let response;
  try {
    response = await fetch(openApiUrl, {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "TimeoutError") {
      throw new Error(`OpenAPI request timed out after ${timeoutMs} ms`);
    }
    throw error;
  }
  if (!response.ok) {
    throw new Error(`OpenAPI request failed with HTTP ${response.status}`);
  }

  const schema = await response.text();
  JSON.parse(schema);
  writeFileSync(schemaPath, `${schema.trim()}\n`, "utf8");

  const result = spawnSync(
    process.execPath,
    [cliPath, schemaPath, "--output", candidatePath, "--default-non-nullable", "false"],
    {
      cwd: projectDirectory,
      encoding: "utf8",
    },
  );
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || "OpenAPI generation failed");
  }

  const candidate = readFileSync(candidatePath, "utf8").replace(/\r\n/g, "\n");
  if (mode === "update") {
    writeFileSync(generatedPath, candidate, "utf8");
    console.log(`Updated ${generatedPath} from ${openApiUrl}`);
  } else {
    if (!existsSync(generatedPath)) {
      throw new Error("Generated contract is missing; run npm run api:types");
    }
    const committed = readFileSync(generatedPath, "utf8").replace(/\r\n/g, "\n");
    if (candidate !== committed) {
      throw new Error(
        "Generated API contract is stale; run npm run api:types and commit the result",
      );
    }
    console.log(`API contract matches ${openApiUrl}`);
  }
} finally {
  rmSync(temporaryDirectory, { recursive: true, force: true });
}
