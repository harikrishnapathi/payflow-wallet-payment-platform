import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.ledger_transaction import LedgerTransaction, LedgerTransactionType
from app.services.transaction_service import create_ledger_transaction,get_wallet_account,get_wallet_for_update,fingerprint

def withdraw(db:Session,wallet_id:uuid.UUID,amount:int,idempotency_key:str,description=None):
    wallet=get_wallet_for_update(db,wallet_id)
    fp=fingerprint(transaction_type=LedgerTransactionType.WITHDRAWAL,amount=amount,currency=wallet.currency,source_wallet_id=wallet_id,description=description)
    existing=db.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key==idempotency_key).with_for_update())
    if existing:
        if existing.request_fingerprint!=fp: raise ValueError('Idempotency key was already used for a different request.')
        return existing
    if wallet.status.value!='ACTIVE': raise ValueError('Wallet is not active.')
    if wallet.available_balance<amount: raise ValueError('Insufficient wallet balance.')
    system=db.scalar(select(LedgerAccount).where(LedgerAccount.account_type==LedgerAccountType.SYSTEM,LedgerAccount.currency==wallet.currency,LedgerAccount.wallet_id.is_(None)))
    if not system: raise ValueError('System ledger account not configured.')
    tx=create_ledger_transaction(db,LedgerTransactionType.WITHDRAWAL,get_wallet_account(db,wallet_id),system,amount,idempotency_key,fp,description)
    wallet.available_balance-=amount; db.flush(); return tx
