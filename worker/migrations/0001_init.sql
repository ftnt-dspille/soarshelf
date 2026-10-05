-- Contributors are GitHub accounts; trust tiers live in content/contributors.yaml.
CREATE TABLE users (
  github_id    INTEGER PRIMARY KEY,
  login        TEXT NOT NULL,
  avatar_url   TEXT NOT NULL DEFAULT '',
  account_created_at TEXT NOT NULL,       -- GitHub account creation, for the age gate
  first_seen   TEXT NOT NULL,
  strikes      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE submissions (
  id           TEXT PRIMARY KEY,           -- 32 hex chars
  github_id    INTEGER NOT NULL REFERENCES users(github_id),
  login        TEXT NOT NULL,
  filename     TEXT NOT NULL,
  size         INTEGER NOT NULL,
  sha256       TEXT NOT NULL UNIQUE,
  meta_json    TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'checking',
  decision     TEXT,
  reasons_json TEXT NOT NULL DEFAULT '[]',
  checks_json  TEXT NOT NULL DEFAULT '[]',
  pr_url       TEXT,
  slug         TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX submissions_by_user ON submissions (github_id, created_at);

CREATE TABLE reports (
  slug         TEXT NOT NULL,
  github_id    INTEGER NOT NULL,
  reason       TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (slug, github_id)
);
