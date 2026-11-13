import type { NextConfig } from "next";

// Tailwind CSS runs through PostCSS (postcss.config.mjs) for both Turbopack (dev) and webpack (build).
const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
