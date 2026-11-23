import enum
from sqlalchemy import Column, Integer, SmallInteger, String, Numeric, Date, ForeignKey
from database import Base

class RoleEnum(str, enum.Enum):
    user = "user"
    worker = "worker"
    admin = "admin"

class Bread(Base):
    __tablename__ = "breads"
    type = Column(String(50), primary_key=True, index=True)
    creation_cost = Column(Numeric(6, 2), nullable=False)
    selling_cost = Column(Numeric(6, 2), nullable=False)

class Client(Base):
    __tablename__ = "clients"
    contact_info = Column(String(50), primary_key=True, index=True)
    client_name = Column(String(50), nullable=False)
    favorite_bread = Column(String(50), ForeignKey("breads.type"), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    status = Column(String(10), default=RoleEnum.user.value, nullable=False)

class ProductionStorage(Base):
    __tablename__ = "production_storage"
    id = Column(SmallInteger, primary_key=True, index=True)
    spaces_left = Column(Integer, nullable=False)

class Unit(Base):
    __tablename__ = "units"
    id = Column(SmallInteger, primary_key=True, index=True)
    employee_responsible = Column(String(50), nullable=False)
    flour_left = Column(Numeric(6, 2), nullable=False)

class Order(Base):
    __tablename__ = "orders"
    fiskal_doc = Column(String(10), primary_key=True, index=True)
    client_contacts = Column(String(50), ForeignKey("clients.contact_info"), nullable=False)
    size = Column(Integer, nullable=False)
    bread_type = Column(String(50), ForeignKey("breads.type"), nullable=False)
    stored_at = Column(SmallInteger, ForeignKey("production_storage.id"), nullable=True)
    unit_responsible = Column(SmallInteger, ForeignKey("units.id"), nullable=True)
    payment_date = Column(Date, nullable=False)
    payment_size = Column(Numeric(16, 2), nullable=False)

class SpentOnFav(Base):
    __tablename__ = "spent_on_fav"
    __table_args__ = {"info": {"is_view": True}}
    client = Column(String(50), primary_key=True)
    fav_bread = Column(String(50), nullable=True)
    spent = Column(Numeric(10, 2), nullable=False)
