CREATE TABLE IF NOT EXISTS posts (
  id            SERIAL PRIMARY KEY,
  category      TEXT        NOT NULL CHECK (category IN ('notice', 'free', 'qna')),
  title         TEXT        NOT NULL,
  content       TEXT        NOT NULL,
  author        TEXT        NOT NULL,
  password_hash TEXT        NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ,
  views         INTEGER     NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS posts_category_id_idx ON posts (category, id DESC);

CREATE TABLE IF NOT EXISTS comments (
  id         SERIAL PRIMARY KEY,
  post_id    INTEGER     NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
  author     TEXT        NOT NULL,
  content    TEXT        NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS comments_post_id_idx ON comments (post_id, id);
