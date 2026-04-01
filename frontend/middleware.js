export function middleware() {
  return new Response("Site em manutenção", {
    status: 503,
  });
}

export const config = {
  matcher: "/:path*",
};