/** @type {import('next').NextConfig} */
const nextConfig = {
  // Dev server rewrites — proxies /api/* to backend so CORS isn't an issue.
  // v4 instance talks to backend on :8003; v1 uses :8000, v2 uses :8001.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8003/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;