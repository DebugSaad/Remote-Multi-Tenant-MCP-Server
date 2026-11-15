#!/bin/sh
set -e

# Enforce password authentication (scram-sha-256) on local loopback TCP connections
if [ -f "$PGDATA/pg_hba.conf" ]; then
    sed -i 's/127\.0\.0\.1\/32[[:space:]]*trust/127.0.0.1\/32            scram-sha-256/g' "$PGDATA/pg_hba.conf"
    sed -i 's/::1\/128[[:space:]]*trust/::1\/128                 scram-sha-256/g' "$PGDATA/pg_hba.conf"
fi

# Execute SQL setup via psql using environment variables
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable pgcrypto for UUID generation
    CREATE EXTENSION IF NOT EXISTS pgcrypto;

    -- Create or update app_user with dynamic password from environment
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user WITH LOGIN PASSWORD '$APP_USER_PASSWORD';
        ELSE
            ALTER ROLE app_user WITH PASSWORD '$APP_USER_PASSWORD';
        END IF;
    END
    \$\$;

    -- Create or update app_admin with dynamic password from environment
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_admin') THEN
            CREATE ROLE app_admin WITH LOGIN PASSWORD '$APP_ADMIN_PASSWORD';
        ELSE
            ALTER ROLE app_admin WITH PASSWORD '$APP_ADMIN_PASSWORD';
        END IF;
    END
    \$\$;

    -- Ensure neither role can bypass Row-Level Security
    ALTER ROLE app_user NOBYPASSRLS;
    ALTER ROLE app_admin NOBYPASSRLS;

    -- Grant database connection permissions
    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO app_user;
    GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO app_admin;

    -- Grant public schema permissions
    GRANT USAGE, CREATE ON SCHEMA public TO app_user;
    GRANT USAGE, CREATE ON SCHEMA public TO app_admin;

    -- Default privileges for future tables created in public schema
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;
EOSQL
