import enum, uuid
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
class LedgerEntryType(str,enum.Enum): DEBIT='DEBIT'; CREDIT='CREDIT'
class LedgerEntry(Base):
    __tablename__='ledger_entries'
    __table_args__=(CheckConstraint('amount > 0',name='ck_ledger_entry_amount_positive'),)
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    ledger_transaction_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('ledger_transactions.id',ondelete='RESTRICT'),nullable=False,index=True)
    ledger_account_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('ledger_accounts.id',ondelete='RESTRICT'),nullable=False,index=True)
    entry_type: Mapped[LedgerEntryType]=mapped_column(Enum(LedgerEntryType,name='ledger_entry_type'),nullable=False)
    amount: Mapped[int]=mapped_column(BigInteger,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    transaction: Mapped['LedgerTransaction']=relationship('LedgerTransaction',back_populates='entries')
    account: Mapped['LedgerAccount']=relationship('LedgerAccount',back_populates='entries')
