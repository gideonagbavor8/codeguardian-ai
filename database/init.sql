-- database/init.sql
-- Optional: runs once on first postgres container start.
-- The database is already created by the POSTGRES_DB env var,
-- so this file is a placeholder for any additional GRANTs or extensions.

-- Enable UUID generation (used by gen_random_uuid() default)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
