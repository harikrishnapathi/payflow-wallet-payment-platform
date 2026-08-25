from alembic import op
import sqlalchemy as sa
revision='4c8e7f1a2b3c'; down_revision='9b913f4a98a8'; branch_labels=None; depends_on=None
def upgrade():
    op.add_column('ledger_transactions',sa.Column('request_fingerprint',sa.String(64),nullable=True))
    op.create_unique_constraint('uq_ledger_transaction_idempotency_key','ledger_transactions',['idempotency_key'])
    op.create_check_constraint('ck_wallet_available_nonnegative','wallets','available_balance >= 0')
    op.create_check_constraint('ck_wallet_pending_nonnegative','wallets','pending_balance >= 0')
    op.create_check_constraint('ck_ledger_entry_amount_positive','ledger_entries','amount > 0')
def downgrade():
    op.drop_constraint('ck_ledger_entry_amount_positive','ledger_entries',type_='check')
    op.drop_constraint('ck_wallet_pending_nonnegative','wallets',type_='check')
    op.drop_constraint('ck_wallet_available_nonnegative','wallets',type_='check')
    op.drop_constraint('uq_ledger_transaction_idempotency_key','ledger_transactions',type_='unique')
    op.drop_column('ledger_transactions','request_fingerprint')
