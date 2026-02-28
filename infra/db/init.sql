-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for UUID generation (fallback; app uses uuid7 in Python)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
