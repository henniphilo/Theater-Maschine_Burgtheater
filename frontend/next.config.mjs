/** @type {import('next').NextConfig} */
const apiProxyTarget =
  process.env.API_PROXY_TARGET ??
  (process.env.DOCKER === "1" ? "http://host.docker.internal:8000" : "http://127.0.0.1:8000");

const nextConfig = {
  experimental: {
    typedRoutes: true
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiProxyTarget}/api/v1/:path*`
      }
    ];
  }
};

export default nextConfig;
