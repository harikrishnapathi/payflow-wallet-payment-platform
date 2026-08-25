from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ledger_account import LedgerAccount, LedgerAccountType

def get_or_create_system_account(db:Session,account_type:LedgerAccountType,currency='INR'):
    account=db.scalar(select(LedgerAccount).where(LedgerAccount.account_type==account_type,LedgerAccount.currency==currency,LedgerAccount.wallet_id.is_(None)))
    if account: return account
    account=LedgerAccount(account_type=account_type,currency=currency); db.add(account); db.flush(); return account
