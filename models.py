from pydantic import BaseModel
from typing import Optional

class FundingRate(BaseModel):
    exchange: str
    symbol: str
    rate: float
    timestamp: float

class Opportunity(BaseModel):
    symbol: str
    long_exchange: str
    long_rate: float
    short_exchange: str
    short_rate: float
    spread: float
    annualized_spread: float

    class Config:
        frozen = True  # Immutable for thread safety
