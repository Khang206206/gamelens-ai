import { createHash } from "node:crypto";
import { execFile, spawn } from "node:child_process";
import { cp, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const workspaceDirectory = "/workspace";
const dependencyImageDirectory = "/opt/gamelens-web-dependencies";
const nodeModulesDirectory = path.join(workspaceDirectory, "node_modules");
const nextCacheDirectory = path.join(workspaceDirectory, ".next");
const markerPath = path.join(nodeModulesDirectory, ".gamelens-package-lock.sha256");
const markerVersion = "2";
const execFileAsync = promisify(execFile);

async function sha256(filePath) {
  const contents = await readFile(filePath);
  return createHash("sha256").update(contents).digest("hex");
}

async function clearDependencyVolume() {
  if (nodeModulesDirectory !== "/workspace/node_modules") {
    throw new Error(`Refusing to clear unexpected path: ${nodeModulesDirectory}`);
  }

  await mkdir(nodeModulesDirectory, { recursive: true });
  const entries = await readdir(nodeModulesDirectory);
  await Promise.all(
    entries.map((entry) =>
      rm(path.join(nodeModulesDirectory, entry), {
        recursive: true,
        force: true,
      }),
    ),
  );
}

async function clearNextCache() {
  if (nextCacheDirectory !== "/workspace/.next") {
    throw new Error(`Refusing to clear unexpected path: ${nextCacheDirectory}`);
  }

  await mkdir(nextCacheDirectory, { recursive: true });
  const entries = await readdir(nextCacheDirectory);
  await Promise.all(
    entries.map((entry) =>
      rm(path.join(nextCacheDirectory, entry), {
        recursive: true,
        force: true,
      }),
    ),
  );
}

async function synchronizeDependencies() {
  const workspaceLock = path.join(workspaceDirectory, "package-lock.json");
  const imageLock = path.join(dependencyImageDirectory, "package-lock.json");
  const [workspaceHash, imageHash] = await Promise.all([
    sha256(workspaceLock),
    sha256(imageLock),
  ]);

  if (workspaceHash !== imageHash) {
    throw new Error(
      [
        "The bind-mounted package-lock.json does not match the web image.",
        "Rebuild it with `docker compose build web` before starting the service.",
      ].join(" "),
    );
  }

  const expectedMarker = `${markerVersion}:${workspaceHash}`;
  const currentMarker = await readFile(markerPath, "utf8").catch(() => "");
  if (currentMarker.trim() === expectedMarker) {
    console.log("[web] Dependency volume matches package-lock.json.");
    return false;
  }

  console.log("[web] Synchronizing node_modules from the locked web image...");
  await clearDependencyVolume();
  await cp(path.join(dependencyImageDirectory, "node_modules"), nodeModulesDirectory, {
    recursive: true,
  });
  await writeFile(markerPath, `${expectedMarker}\n`, "utf8");
  console.log("[web] Dependency volume synchronized.");
  return true;
}

async function prepareRuntimeOwnership(dependenciesChanged) {
  if (process.getuid?.() !== 0) return;

  await mkdir(nextCacheDirectory, { recursive: true });
  if (dependenciesChanged) {
    console.log("[web] Clearing the Next.js cache after dependency synchronization...");
    await clearNextCache();
  }

  const [dependencyStats, cacheStats] = await Promise.all([
    stat(nodeModulesDirectory),
    stat(nextCacheDirectory),
  ]);

  if (dependenciesChanged || dependencyStats.uid !== 1000) {
    await execFileAsync("chown", ["-R", "node:node", nodeModulesDirectory]);
  }
  if (cacheStats.uid !== 1000) {
    await execFileAsync("chown", ["-R", "node:node", nextCacheDirectory]);
  }

  process.setgid("node");
  process.setuid("node");
  console.log("[web] Development server privileges dropped to the node user.");
}

async function main() {
  const dependenciesChanged = await synchronizeDependencies();
  await prepareRuntimeOwnership(dependenciesChanged);

  const developmentServer = spawn("npm", ["run", "dev", "--", "--hostname", "0.0.0.0"], {
    cwd: workspaceDirectory,
    env: process.env,
    stdio: "inherit",
  });
  let requestedShutdown = null;

  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => {
      if (requestedShutdown) return;
      requestedShutdown = signal;
      developmentServer.kill(signal);
    });
  }

  developmentServer.on("error", (error) => {
    console.error(`[web] Failed to start Next.js: ${error.message}`);
    process.exitCode = 1;
  });

  developmentServer.on("exit", (code, signal) => {
    if (signal) {
      if (signal === requestedShutdown) {
        console.log(`[web] Next.js stopped cleanly after receiving ${signal}.`);
        process.exitCode = 0;
        return;
      }

      console.error(`[web] Next.js stopped after receiving ${signal}.`);
      process.exitCode = 1;
      return;
    }

    process.exitCode = code ?? 1;
  });
}

main().catch((error) => {
  console.error(`[web] Startup failed: ${error.message}`);
  process.exitCode = 1;
});
