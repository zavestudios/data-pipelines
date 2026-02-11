from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawListing(BaseModel):
    model_config = ConfigDict(extra="ignore")

    address: Optional[str] = None
    price: Optional[str] = None
    source_file: Optional[str] = None


class NormalizedListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    source_file: str = Field(min_length=1)
    run_date: str = Field(min_length=10)

    @field_validator("address")
    @classmethod
    def _strip_address(cls, value: str) -> str:
        return value.strip()


@dataclass(frozen=True)
class RejectedRecord:
    record: dict
    reason: str


class LoadResult(BaseModel):
    inserted: int
    updated: int
    rejected: int
    processed: int
