from app.db.session import SessionLocal
from app.models.ledger_account import LedgerAccountType
from app.services.system_account_service import get_or_create_system_account
def main():
 db=SessionLocal()
 try:
  for t in (LedgerAccountType.SYSTEM,LedgerAccountType.PLATFORM,LedgerAccountType.FEES): print(f'{t.value}: {get_or_create_system_account(db,t).id}')
  db.commit()
 finally: db.close()
if __name__=='__main__': main()
