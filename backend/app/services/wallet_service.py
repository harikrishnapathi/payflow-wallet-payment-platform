from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.ledger_account import LedgerAccount, LedgerAccountType
from app.models.user import User
from app.models.wallet import Wallet

def create_user_wallet(db:Session,user:User)->Wallet:
    existing=db.scalar(select(Wallet).where(Wallet.user_id==user.id))
    if existing: return existing
    wallet=Wallet(user_id=user.id,currency='INR',available_balance=0,pending_balance=0)
    db.add(wallet); db.flush()
    db.add(LedgerAccount(wallet_id=wallet.id,account_type=LedgerAccountType.USER_WALLET,currency='INR'))
    db.flush(); return wallet
