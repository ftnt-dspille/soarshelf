// /downloads/<slug>/<file> on the site's own origin. Serves the static file
// exactly as before and, for the package itself, bumps a per-item per-day
// counter in D1. No IP, user agent or cookie is stored. Icons and screenshots
// are fetched on every page view, so they are passed through uncounted.
interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  DB?: { prepare(sql: string): { bind(...v: unknown[]): { run(): Promise<unknown> } } };
}

const PACKAGE_FILE = /\.(json|zip|tgz|tar\.gz)$/i;

/** The item slug when this path is a package download worth counting, else null. */
export function countedSlug(pathname: string): string | null {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length !== 3 || parts[0] !== 'downloads') return null;
  const [, slug, file] = parts;
  if (!/^[a-z0-9][a-z0-9-]*$/.test(slug) || !PACKAGE_FILE.test(file)) return null;
  return slug;
}

export const onRequest = async ({
  request,
  env,
  waitUntil,
}: {
  request: Request;
  env: Env;
  waitUntil: (p: Promise<unknown>) => void;
}): Promise<Response> => {
  const res = await env.ASSETS.fetch(request);
  const slug = request.method === 'GET' && res.status === 200 && env.DB ? countedSlug(new URL(request.url).pathname) : null;
  if (slug && env.DB) {
    const day = new Date().toISOString().slice(0, 10);
    waitUntil(
      env.DB.prepare('INSERT INTO download_counts (slug, day, n) VALUES (?1, ?2, 1) ON CONFLICT (slug, day) DO UPDATE SET n = n + 1')
        .bind(slug, day)
        .run()
        .catch(() => undefined), // a counting failure never breaks a download
    );
  }
  return res;
};
