import { applyD1Migrations, env, type D1Migration } from 'cloudflare:test';

const t = env as unknown as { DB: D1Database; TEST_MIGRATIONS: D1Migration[] };
await applyD1Migrations(t.DB, t.TEST_MIGRATIONS);
