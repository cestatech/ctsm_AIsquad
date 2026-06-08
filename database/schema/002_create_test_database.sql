-- Test database for pytest when using Docker Postgres on host port 5433.
-- Executed only on first container init (empty volume).
CREATE DATABASE celerius_test OWNER celerius;
