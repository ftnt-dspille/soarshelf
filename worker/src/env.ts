export interface Env {
  DB: D1Database;
  QUARANTINE: R2Bucket;

  SITE_ORIGIN: string; // e.g. https://soarshelf.example (no trailing slash)
  REPO: string; // owner/name of the content repository

  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  GITHUB_APP_ID: string;
  GITHUB_APP_INSTALLATION_ID: string;
  GITHUB_APP_PRIVATE_KEY: string; // PKCS#8 PEM

  SESSION_SECRET: string;
  TURNSTILE_SECRET: string;
  INTERNAL_TOKEN: string;

  /** "1" only in local .dev.vars: sign in as a fixed user without GitHub, on localhost only. */
  DEV_LOGIN?: string;
}

export type Trust = 'new' | 'contributor' | 'trusted' | 'maintainer';

export interface Session {
  id: number;
  login: string;
  avatar: string;
  /** GitHub account creation time (ISO), for the account-age gate. */
  created: string;
  /** Expiry, seconds since epoch. */
  exp: number;
}
