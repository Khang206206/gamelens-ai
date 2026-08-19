import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  typedRoutes: true,
  allowedDevOrigins: ["localhost", "127.0.0.1", "web", "e2e-web", "gamelens.test"],
};

export default nextConfig;
