from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

AssetType = Literal[
    "server",
    "service",
    "endpoint",
    "certificate",
    "pipeline",
    "backup",
    "library",
    "vendor_product",
    "other",
]


class AssetBase(BaseModel):
    asset_type: AssetType = Field(..., description="Logical asset category.")
    name: str = Field(..., min_length=1, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    criticality: Optional[int] = Field(default=None, ge=1, le=5)
    environment: Optional[str] = Field(default=None, max_length=50)
    vendor: Optional[str] = Field(default=None, max_length=255)
    lifecycle_years: Optional[int] = Field(default=None, ge=0, le=50)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_type: Optional[AssetType] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    criticality: Optional[int] = Field(default=None, ge=1, le=5)
    environment: Optional[str] = Field(default=None, max_length=50)
    vendor: Optional[str] = Field(default=None, max_length=255)
    lifecycle_years: Optional[int] = Field(default=None, ge=0, le=50)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class Asset(AssetBase):
    id: str


class ScanIngestRequest(BaseModel):
    source: Literal["host", "network", "repo", "manual"]
    assets: list[AssetCreate]


class ScanIngestResponse(BaseModel):
    source: str
    created: int
    asset_ids: list[str]
