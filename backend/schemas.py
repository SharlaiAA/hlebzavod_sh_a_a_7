from pydantic import BaseModel
from typing import Optional
from datetime import date
from decimal import Decimal
from models import RoleEnum

class ClientRegister(BaseModel):
    contact_info: str
    client_name: str
    password: str
    favorite_bread: Optional[str] = None

class ClientUpdate(BaseModel):
    client_name: Optional[str] = None
    favorite_bread: Optional[str] = None
    status: Optional[RoleEnum] = None
    password: Optional[str] = None

class ClientOut(BaseModel):
    contact_info: str
    client_name: str
    favorite_bread: Optional[str]
    status: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class OrderUserCreate(BaseModel):
    fiskal_doc: str
    bread_type: str
    size: int
    payment_date: date

class OrderAdminCreate(OrderUserCreate):
    client_contacts: str
    stored_at: Optional[int] = None
    unit_responsible: Optional[int] = None
    payment_size: Decimal

class OrderUpdate(BaseModel):
    size: Optional[int] = None
    bread_type: Optional[str] = None
    stored_at: Optional[int] = None
    unit_responsible: Optional[int] = None
    payment_date: Optional[date] = None
    payment_size: Optional[Decimal] = None

class OrderOut(BaseModel):
    fiskal_doc: str
    client_contacts: str
    size: int
    bread_type: str
    stored_at: Optional[int]
    unit_responsible: Optional[int]
    payment_date: date
    payment_size: Decimal
    class Config:
        from_attributes = True

class UnitSchema(BaseModel):
    id: int
    employee_responsible: str
    flour_left: Decimal
    class Config:
        from_attributes = True

class StorageSchema(BaseModel):
    id: int
    spaces_left: int
    class Config:
        from_attributes = True

class BreadSchema(BaseModel):
    type: str
    creation_cost: Decimal
    selling_cost: Decimal
    class Config:
        from_attributes = True

class SpentOnFavOut(BaseModel):
    client: str
    fav_bread: Optional[str]
    spent: Decimal
    class Config:
        from_attributes = True

class TestClientsSeed(BaseModel):
    n: int
