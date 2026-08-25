import uuid
from datetime import datetime
from pydantic import BaseModel,ConfigDict
class WalletResponse(BaseModel): model_config=ConfigDict(from_attributes=True); id:uuid.UUID; user_id:uuid.UUID; currency:str; available_balance:int; pending_balance:int; status:str; created_at:datetime; updated_at:datetime
