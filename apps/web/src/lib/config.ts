const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

export interface PublicConfig {
  apiBaseUrl: string;
}

export function validateApiBaseUrl(value: string | undefined): string {
  if (!value?.trim()) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is required. Copy .env.example to .env.local and set an HTTP(S) API base URL.",
    );
  }

  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error("NEXT_PUBLIC_API_URL must be an absolute HTTP(S) URL.");
  }

  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error("NEXT_PUBLIC_API_URL must use http:// or https://.");
  }
  if (!url.hostname) {
    throw new Error("NEXT_PUBLIC_API_URL must include a host.");
  }
  if (url.username || url.password) {
    throw new Error("NEXT_PUBLIC_API_URL must not contain credentials.");
  }
  if (url.search || url.hash) {
    throw new Error("NEXT_PUBLIC_API_URL must not contain a query string or fragment.");
  }

  const normalizedPath = url.pathname.replace(/\/+$/, "");
  return `${url.origin}${normalizedPath}`;
}

export function getPublicConfig(): PublicConfig {
  return {
    apiBaseUrl: validateApiBaseUrl(process.env.NEXT_PUBLIC_API_URL),
  };
}
