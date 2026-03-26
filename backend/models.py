from pydantic import BaseModel, Field
from typing import Any, Optional
import json


class PartCreate(BaseModel):
    category: str
    brand: str
    name: str
    model: str
    specs: dict = {}
    tdp: int = 0
    benchmark_score: int = 0
    reference_price: int = 0
    release_year: Optional[int] = None
    notes: str = ""


class PartUpdate(BaseModel):
    category: Optional[str] = None
    brand: Optional[str] = None
    name: Optional[str] = None
    model: Optional[str] = None
    specs: Optional[dict] = None
    tdp: Optional[int] = None
    benchmark_score: Optional[int] = None
    reference_price: Optional[int] = None
    release_year: Optional[int] = None
    notes: Optional[str] = None


class BuildCreate(BaseModel):
    name: str
    description: str = ""
    purpose: str = "balanced"
    budget: int = 0


class BuildUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    purpose: Optional[str] = None
    budget: Optional[int] = None


class BuildPartAdd(BaseModel):
    part_id: int
    quantity: int = 1
    custom_price: Optional[int] = None
    is_used: bool = False


class SuggestRequest(BaseModel):
    budget: int
    purpose: str = "gaming"
    prefer_new: bool = True
    include_used: bool = False
