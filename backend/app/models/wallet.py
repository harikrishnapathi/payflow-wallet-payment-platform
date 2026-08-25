import enum, uuid
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base
class WalletStatus(str, enum.Enum): ACTIVE='ACTIVE'; SUSPENDED='SUSPENDED'; CLOSED='CLOSED'
class Wallet(Base):
    __tablename__='wallets'
    __table_args__=(CheckConstraint('available_balance >= 0',name='ck_wallet_available_nonnegative'), CheckConstraint('pending_balance >= 0',name='ck_wallet_pending_nonnegative'))
    id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey('users.id',ondelete='CASCADE'),unique=True,nullable=False,index=True)
    currency: Mapped[str]=mapped_column(String(3),default='INR',nullable=False)
    available_balance: Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    pending_balance: Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    status: Mapped[WalletStatus]=mapped_column(Enum(WalletStatus,name='wallet_status'),default=WalletStatus.ACTIVE,nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),nullable=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now(),nullable=False)
    user: Mapped['User']=relationship('User',back_populates='wallet')
    ledger_account: Mapped['LedgerAccount|None']=relationship('LedgerAccount',back_populates='wallet',uselist=False,cascade='all, delete-orphan')
