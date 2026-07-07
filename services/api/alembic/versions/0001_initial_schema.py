"""initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-07-07 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # 2. Enums
    sa.Enum('owner', 'admin', 'member', 'client_viewer', name='roleenum').create(op.get_bind())
    sa.Enum('saas', 'local_service', 'ecommerce', 'publisher', 'agency', name='industryenum').create(op.get_bind())
    sa.Enum('queued', 'crawling', 'analyzing', 'done', 'partial', 'failed', name='auditstatusenum').create(op.get_bind())
    sa.Enum('full', 'single_page', name='auditmodeenum').create(op.get_bind())
    sa.Enum('pass', 'fail', 'warn', 'info', name='findingstatusenum').create(op.get_bind())
    sa.Enum('critical', 'high', 'medium', 'low', name='findingseverityenum').create(op.get_bind())
    sa.Enum('content', 'technical', 'onpage', 'schema', 'performance', 'ai_readiness', 'images', 'local', name='findingcategoryenum').create(op.get_bind())
    sa.Enum('immediate', 'one_week', 'one_month', 'backlog', name='findingeffortenum').create(op.get_bind())
    sa.Enum('informational', 'commercial', 'transactional', 'navigational', name='keywordintentenum').create(op.get_bind())
    sa.Enum('gsc', 'ga4', 'gbp', name='oauthproviderenum').create(op.get_bind())

    # 3. Tables
    op.create_table('organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=True),
        sa.Column('google_sub', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('google_sub')
    )
    
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('prefix', sa.String(length=8), nullable=False),
        sa.Column('hash', sa.LargeBinary(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('credit_ledger',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('delta', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=60), nullable=False),
        sa.Column('ref_type', sa.String(length=30), nullable=True),
        sa.Column('ref_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_credit_ledger_org_id', 'credit_ledger', ['org_id'], unique=False)
    
    op.create_table('memberships',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'member', 'client_viewer', name='roleenum'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'org_id')
    )
    
    op.create_table('oauth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('gsc', 'ga4', 'gbp', name='oauthproviderenum'), nullable=False),
        sa.Column('encrypted_refresh_token', sa.LargeBinary(), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('domain', postgresql.CITEXT(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('industry', sa.Enum('saas', 'local_service', 'ecommerce', 'publisher', 'agency', name='industryenum'), nullable=True),
        sa.Column('gsc_connected', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'domain', name='uq_project_org_domain')
    )
    
    op.create_table('audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('queued', 'crawling', 'analyzing', 'done', 'partial', 'failed', name='auditstatusenum'), nullable=False),
        sa.Column('mode', sa.Enum('full', 'single_page', name='auditmodeenum'), nullable=False),
        sa.Column('page_limit', sa.Integer(), nullable=False),
        sa.Column('root_url', sa.Text(), nullable=False),
        sa.Column('score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('category_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('keyword_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('set_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('term', postgresql.CITEXT(), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('language', sa.String(length=2), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=True),
        sa.Column('difficulty', sa.Numeric(), nullable=True),
        sa.Column('cpc', sa.Numeric(), nullable=True),
        sa.Column('intent', sa.Enum('informational', 'commercial', 'transactional', 'navigational', name='keywordintentenum'), nullable=True),
        sa.Column('opportunity_score', sa.Numeric(), nullable=True),
        sa.Column('serp_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('refreshed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['set_id'], ['keyword_sets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('rendered', sa.Boolean(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('h1', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('snapshot_key', sa.Text(), nullable=True),
        sa.Column('screenshot_key', sa.Text(), nullable=True),
        sa.Column('lab_vitals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['audits.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_pages_audit_id', 'pages', ['audit_id'], unique=False)
    
    op.create_table('drift_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_url', sa.Text(), nullable=False),
        sa.Column('rule', sa.String(length=60), nullable=False),
        sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('acknowledged', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_drift_events_project_id_acknowledged', 'drift_events', ['project_id', 'acknowledged'], unique=False)
    
    op.create_table('baselines',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_url', sa.Text(), nullable=False),
        sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agent', sa.String(length=40), nullable=False),
        sa.Column('check_id', sa.String(length=80), nullable=False),
        sa.Column('status', sa.Enum('pass', 'fail', 'warn', 'info', name='findingstatusenum'), nullable=False),
        sa.Column('severity', sa.Enum('critical', 'high', 'medium', 'low', name='findingseverityenum'), nullable=True),
        sa.Column('category', sa.Enum('content', 'technical', 'onpage', 'schema', 'performance', 'ai_readiness', 'images', 'local', name='findingcategoryenum'), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fix', sa.Text(), nullable=True),
        sa.Column('fix_code', sa.Text(), nullable=True),
        sa.Column('effort', sa.Enum('immediate', 'one_week', 'one_month', 'backlog', name='findingeffortenum'), nullable=True),
        sa.ForeignKeyConstraint(['audit_id'], ['audits.id'], ),
        sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_findings_audit_id_severity', 'findings', ['audit_id', 'severity'], unique=False)
    
    # 4. Partitioned table
    op.execute("""
        CREATE TABLE rank_snapshots (
            id BIGSERIAL,
            keyword_id UUID NOT NULL,
            position INTEGER,
            url TEXT,
            serp_features TEXT[],
            captured_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id, captured_at),
            CONSTRAINT fk_rank_snapshots_keyword_id FOREIGN KEY (keyword_id) REFERENCES keywords (id)
        ) PARTITION BY RANGE (captured_at);
    """)
    op.execute("CREATE INDEX ix_rank_snapshots_keyword_id_captured_at_desc ON rank_snapshots USING btree (keyword_id, captured_at DESC);")
    
    # Create the first 3 months partitions helper
    op.execute("""
        CREATE OR REPLACE FUNCTION create_rank_snapshots_partitions() RETURNS void AS 
        DECLARE
            start_date date := date_trunc('month', current_date);
            end_date date;
            partition_name text;
        BEGIN
            FOR i IN 0..2 LOOP
                start_date := date_trunc('month', current_date + (i || ' month')::interval);
                end_date := start_date + interval '1 month';
                partition_name := 'rank_snapshots_' || to_char(start_date, 'YYYY_MM');
                
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS %I PARTITION OF rank_snapshots FOR VALUES FROM (%L) TO (%L);',
                    partition_name, start_date, end_date
                );
            END LOOP;
        END;
         LANGUAGE plpgsql;
    """)
    op.execute("SELECT create_rank_snapshots_partitions();")


def downgrade() -> None:
    # Drop tables
    op.execute("DROP TABLE IF EXISTS rank_snapshots CASCADE;")
    op.drop_index('ix_findings_audit_id_severity', table_name='findings')
    op.drop_table('findings')
    op.drop_table('baselines')
    op.drop_index('ix_drift_events_project_id_acknowledged', table_name='drift_events')
    op.drop_table('drift_events')
    op.drop_index('ix_pages_audit_id', table_name='pages')
    op.drop_table('pages')
    op.drop_table('keywords')
    op.drop_table('keyword_sets')
    op.drop_table('audits')
    op.drop_table('projects')
    op.drop_table('oauth_tokens')
    op.drop_table('memberships')
    op.drop_index('ix_credit_ledger_org_id', table_name='credit_ledger')
    op.drop_table('credit_ledger')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('organizations')
    
    # Drop enums
    sa.Enum('owner', 'admin', 'member', 'client_viewer', name='roleenum').drop(op.get_bind())
    sa.Enum('saas', 'local_service', 'ecommerce', 'publisher', 'agency', name='industryenum').drop(op.get_bind())
    sa.Enum('queued', 'crawling', 'analyzing', 'done', 'partial', 'failed', name='auditstatusenum').drop(op.get_bind())
    sa.Enum('full', 'single_page', name='auditmodeenum').drop(op.get_bind())
    sa.Enum('pass', 'fail', 'warn', 'info', name='findingstatusenum').drop(op.get_bind())
    sa.Enum('critical', 'high', 'medium', 'low', name='findingseverityenum').drop(op.get_bind())
    sa.Enum('content', 'technical', 'onpage', 'schema', 'performance', 'ai_readiness', 'images', 'local', name='findingcategoryenum').drop(op.get_bind())
    sa.Enum('immediate', 'one_week', 'one_month', 'backlog', name='findingeffortenum').drop(op.get_bind())
    sa.Enum('informational', 'commercial', 'transactional', 'navigational', name='keywordintentenum').drop(op.get_bind())
    sa.Enum('gsc', 'ga4', 'gbp', name='oauthproviderenum').drop(op.get_bind())

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS citext;")
