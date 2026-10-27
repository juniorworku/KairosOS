"""Authentication, sessions, plans and audit records. Frozen M1 schema."""

from alembic import op

revision: str = "0002_auth"
down_revision: str = "0001_foundation"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE magic_link_tokens (\n\tid UUID NOT NULL, \n\temail VARCHAR(254) NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tconsumed_at TIMESTAMP WITH TIME ZONE, \n\tcreated_ip_hash VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (token_hash)\n)"
    )
    op.execute("CREATE INDEX ix_magic_link_tokens_email ON magic_link_tokens (email)")
    op.execute(
        "CREATE TABLE oauth_states (\n\tid VARCHAR(64) NOT NULL, \n\tcode_verifier VARCHAR(128) NOT NULL, \n\tnonce_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tconsumed_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id)\n)"
    )
    op.execute(
        "CREATE TABLE owner_seed_markers (\n\temail_hash VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (email_hash)\n)"
    )
    op.execute(
        "CREATE TABLE plans (\n\tid UUID NOT NULL, \n\tkey VARCHAR(30) NOT NULL, \n\tname VARCHAR(80) NOT NULL, \n\tquotas JSON NOT NULL, \n\tentitlements JSON NOT NULL, \n\tis_default BOOLEAN NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (key)\n)"
    )
    op.execute(
        "CREATE TABLE users (\n\tid UUID NOT NULL, \n\temail VARCHAR(254) NOT NULL, \n\tname VARCHAR(120) NOT NULL, \n\tavatar_url VARCHAR(1000), \n\ttimezone VARCHAR(80) NOT NULL, \n\twork_days JSON NOT NULL, \n\twork_start VARCHAR(5) NOT NULL, \n\twork_end VARCHAR(5) NOT NULL, \n\tdaily_max_focus_minutes INTEGER NOT NULL, \n\tenergy_peak VARCHAR(20) NOT NULL, \n\tai_enabled BOOLEAN NOT NULL, \n\tplan_id UUID NOT NULL, \n\trole VARCHAR(20) NOT NULL, \n\temail_verified_at TIMESTAMP WITH TIME ZONE, \n\tdisabled_at TIMESTAMP WITH TIME ZONE, \n\tonboarding_completed_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(plan_id) REFERENCES plans (id)\n)"
    )
    op.execute("CREATE UNIQUE INDEX ix_users_email ON users (email)")
    op.execute(
        "CREATE TABLE audit_log (\n\tid UUID NOT NULL, \n\tactor_user_id UUID, \n\taction VARCHAR(80) NOT NULL, \n\ttarget_type VARCHAR(40) NOT NULL, \n\ttarget_id VARCHAR(80) NOT NULL, \n\tmetadata JSON NOT NULL, \n\tip_hash VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL\n)"
    )
    op.execute(
        "CREATE TABLE auth_identities (\n\tid UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tprovider VARCHAR(20) NOT NULL, \n\tprovider_user_id VARCHAR(254) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider, provider_user_id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)"
    )
    op.execute("CREATE INDEX ix_auth_identities_user_id ON auth_identities (user_id)")
    op.execute(
        "CREATE TABLE invites (\n\tid UUID NOT NULL, \n\temail VARCHAR(254) NOT NULL, \n\tinvited_by UUID, \n\trole VARCHAR(20) NOT NULL, \n\tplan_id UUID NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tused_at TIMESTAMP WITH TIME ZONE, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(invited_by) REFERENCES users (id) ON DELETE SET NULL, \n\tFOREIGN KEY(plan_id) REFERENCES plans (id), \n\tUNIQUE (token_hash)\n)"
    )
    op.execute("CREATE INDEX ix_invites_email ON invites (email)")
    op.execute(
        "CREATE TABLE sessions (\n\tid UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\tcsrf_hash VARCHAR(64) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tabsolute_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tlast_used_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tuser_agent VARCHAR(300) NOT NULL, \n\tip_hash VARCHAR(64) NOT NULL, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, \n\tUNIQUE (token_hash)\n)"
    )
    op.execute("CREATE INDEX ix_sessions_user_id ON sessions (user_id)")


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("invites")
    op.drop_table("auth_identities")
    op.drop_table("audit_log")
    op.drop_table("users")
    op.drop_table("plans")
    op.drop_table("owner_seed_markers")
    op.drop_table("oauth_states")
    op.drop_table("magic_link_tokens")
