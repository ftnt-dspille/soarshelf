// /api/* on the site's own origin, handed to the upload Worker through a
// service binding. The Worker has no public URL of its own (workers_dev is
// off), so this is the only way in, and cookies, Origin checks and CSP all
// stay same-origin. Static pages never invoke this function.
interface Env {
  API: { fetch(request: Request): Promise<Response> };
}

export const onRequest = ({ request, env }: { request: Request; env: Env }): Promise<Response> =>
  env.API.fetch(new Request(request, { redirect: 'manual' }));
