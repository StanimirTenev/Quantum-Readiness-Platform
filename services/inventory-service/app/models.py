from pydantic import BaseModel
from typing import Optional

class Asset(BaseModel):
    id: Optional[str] = None
    asset_type: str
    name: str
    owner: Optional[str] = None
    criticality: Optional[int] = None
    environment: Optional[str] = None
    vendor: Optional[str] = None
