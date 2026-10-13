-- Download counts per item per day. No visitor data: just how many times a
-- package was fetched, written by the site's /downloads Pages Function.
CREATE TABLE download_counts (
  slug  TEXT NOT NULL,
  day   TEXT NOT NULL,                     -- UTC date, YYYY-MM-DD
  n     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (slug, day)
);
