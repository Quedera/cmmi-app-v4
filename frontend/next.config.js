/** @type {import('next').NextConfig} */
const nextConfig = {
  // /api/* -> backend.
  //
  // The backend URL is baked in at BUILD time via NEXT_PUBLIC_API_URL (the
  // Dockerfile passes it as a build arg). It must NOT be a hardcoded
  // localhost: on Azure the frontend and backend are two separate container
  // apps, so the frontend can only reach the backend over its FQDN.
  // The default keeps the on-prem systemd deployment working (backend :8003).
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8003';
    return [
      {
        source: '/api/:path*',
        destination: backendUrl + '/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;