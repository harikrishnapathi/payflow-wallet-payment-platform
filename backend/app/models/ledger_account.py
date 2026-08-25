import enum, uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
class LedgerAccountType(str,enum.Enum): USER_WALLET='USER_WALLET'; PLATFORM='PLATFORM'; FEES='FEES'; SYSTEM='SYSTEM'
class LedgerAccount(Base):
    __tablename__='ledger_accounts'
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    wallet_id: Mapped[uuid.UUID|None]=mapped_column(UUID(as_uuid=True),ForeignKey('wallets.id',ondelete='CASCADE'),unique=True,nullable=True,index=True)
    account_type: Mapped[LedgerAccountType]=mapped_column(Enum(LedgerAccountType,name='ledger_account_type'),nullable=False)
    currency: Mapped[str]=mapped_column(String(3),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    wallet: Mapped['Wallet|None']=relationship('Wallet',back_populates='ledger_account')
    entries: Mapped[list['LedgerEntry']]=relationship('LedgerEntry',back_populates='account')
