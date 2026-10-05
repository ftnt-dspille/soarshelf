import type { Env } from './env';
import { HttpError, fail } from './http';
import * as auth from './auth';
import * as submissions from './submissions';
import * as internal from './internal';
import { report } from './reports';

type Handler = (req: Request, env: Env, ...params: string[]) => Promise<Response>;

const routes: [string, RegExp, Handler][] = [
  ['GET', /^\/api\/auth\/login$/, auth.login],
  ['GET', /^\/api\/auth\/callback$/, auth.callback],
  ['POST', /^\/api\/auth\/logout$/, auth.logout],
  ['GET', /^\/api\/me$/, auth.me],
  ['POST', /^\/api\/submissions$/, submissions.create],
  ['GET', /^\/api\/submissions$/, submissions.list],
  ['GET', /^\/api\/submissions\/([^/]+)$/, submissions.get],
  ['POST', /^\/api\/reports$/, report],
  ['GET', /^\/api\/internal\/submissions\/([^/]+)$/, internal.meta],
  ['GET', /^\/api\/internal\/submissions\/([^/]+)\/file$/, internal.file],
  ['POST', /^\/api\/internal\/submissions\/([^/]+)\/result$/, internal.result]
];

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const path = new URL(req.url).pathname;
    try {
      for (const [method, pattern, handler] of routes) {
        const m = pattern.exec(path);
        if (m && req.method === method) return await handler(req, env, ...m.slice(1));
      }
      return fail(404, 'Not found');
    } catch (e) {
      if (e instanceof HttpError) return fail(e.status, e.message, e.extra);
      console.error(e);
      return fail(500, 'Something went wrong');
    }
  }
} satisfies ExportedHandler<Env>;
