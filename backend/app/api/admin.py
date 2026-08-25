from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,func,case
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User,UserRole
from app.models.ledger_entry import LedgerEntry,LedgerEntryType
from app.models.ledger_transaction import LedgerTransaction
router=APIRouter(prefix='/admin',tags=['Admin'])
def admin(user=Depends(get_current_user)):
    if user.role!=UserRole.ADMIN: raise HTTPException(403,'Admin access required.')
    return user
@router.get('/ledger/reconciliation')
def reconciliation(_:User=Depends(admin),db:Session=Depends(get_db)):
    rows=db.execute(select(LedgerTransaction.id,func.sum(case((LedgerEntry.entry_type==LedgerEntryType.DEBIT,LedgerEntry.amount),else_=0)).label('debits'),func.sum(case((LedgerEntry.entry_type==LedgerEntryType.CREDIT,LedgerEntry.amount),else_=0)).label('credits')).join(LedgerEntry).group_by(LedgerTransaction.id)).all()
    mismatches=[{'transaction_id':str(r.id),'debits':r.debits or 0,'credits':r.credits or 0} for r in rows if (r.debits or 0)!=(r.credits or 0)]
    return {'status':'ok' if not mismatches else 'mismatch','transactions_checked':len(rows),'mismatches':mismatches}
