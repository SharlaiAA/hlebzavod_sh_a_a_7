import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from decimal import Decimal
import psycopg

import models, schemas, auth
from database import engine, get_db, AsyncSessionLocal, PSYCOPG_DATABASE_URL

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        tables_to_create = [
            table for table in models.Base.metadata.tables.values()
            if not table.info.get("is_view")
        ]
        await conn.run_sync(models.Base.metadata.create_all, tables=tables_to_create)

    admin_contact = os.getenv("ADMIN_CONTACT")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME")

    if admin_contact and admin_password:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(models.Client).filter(models.Client.contact_info == admin_contact)
            )
            if not result.scalar_one_or_none():
                admin_user = models.Client(
                    contact_info=admin_contact,
                    client_name=admin_name,
                    hashed_password=auth.get_password_hash(admin_password),
                    status=models.RoleEnum.admin.value,
                )
                session.add(admin_user)
                await session.commit()
    yield


app = FastAPI(title="APIshka", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.post("/register", response_model=schemas.ClientOut)
async def register(client_data: schemas.ClientRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Client).filter(models.Client.contact_info == client_data.contact_info))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь с таким contact_info уже существует")
    
    new_client = models.Client(
        contact_info=client_data.contact_info,
        client_name=client_data.client_name,
        favorite_bread=client_data.favorite_bread,
        hashed_password=auth.get_password_hash(client_data.password),
        status=models.RoleEnum.user.value,
    )
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return new_client


@app.post("/login", response_model=schemas.Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Client).filter(models.Client.contact_info == form_data.username))
    client = result.scalar_one_or_none()
    if not client or not auth.verify_password(form_data.password, client.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный contact_info или пароль")
    
    access_token = auth.create_access_token(data={"sub": client.contact_info, "status": client.status})
    return {"access_token": access_token, "token_type": "bearer"}


async def get_worker_unit_ids(db: AsyncSession, worker_name: str) -> List[int]:
    result = await db.execute(select(models.Unit.id).filter(models.Unit.employee_responsible == worker_name))
    return list(result.scalars().all())


@app.get("/orders", response_model=List[schemas.OrderOut])
async def get_orders(
    db: AsyncSession = Depends(get_db),
    current_client: models.Client = Depends(auth.get_current_client)
):
    if current_client.status == models.RoleEnum.admin.value:
        result = await db.execute(select(models.Order))
        return result.scalars().all()
    elif current_client.status == models.RoleEnum.worker.value:
        unit_ids = await get_worker_unit_ids(db, current_client.client_name)
        result = await db.execute(select(models.Order).filter(models.Order.unit_responsible.in_(unit_ids)))
        return result.scalars().all()
    elif current_client.status == models.RoleEnum.user.value:
        result = await db.execute(select(models.Order).filter(models.Order.client_contacts == current_client.contact_info))
        return result.scalars().all()


@app.post("/orders/my", response_model=schemas.OrderOut)
async def create_order_as_user(
    order_data: schemas.OrderUserCreate,
    db: AsyncSession = Depends(get_db),
    current_client: models.Client = Depends(auth.require_roles([models.RoleEnum.user]))
):
    result = await db.execute(select(models.Bread).filter(models.Bread.type == order_data.bread_type))
    bread = result.scalar_one_or_none()
    if not bread:
        raise HTTPException(status_code=404, detail="Указанный вид хлеба не найден")

    total_price = Decimal(order_data.size) * bread.selling_cost

    new_order = models.Order(
        fiskal_doc=order_data.fiskal_doc,
        client_contacts=current_client.contact_info,
        size=order_data.size,
        bread_type=order_data.bread_type,
        payment_date=order_data.payment_date,
        payment_size=total_price
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    return new_order


@app.post("/orders", response_model=schemas.OrderOut)
async def create_order_as_admin(
    order_data: schemas.OrderAdminCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(auth.require_roles([models.RoleEnum.admin]))
):
    new_order = models.Order(**order_data.model_dump())
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    return new_order


@app.patch("/orders/{fiskal_doc}", response_model=schemas.OrderOut)
async def update_order(
    fiskal_doc: str,
    order_update: schemas.OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_client: models.Client = Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))
):
    result = await db.execute(select(models.Order).filter(models.Order.fiskal_doc == fiskal_doc))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    if current_client.status == models.RoleEnum.worker.value:
        unit_ids = await get_worker_unit_ids(db, current_client.client_name)
        if order.unit_responsible not in unit_ids:
            raise HTTPException(status_code=403, detail="Вы можете изменять заказы только своего цеха")

    update_data = order_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(order, key, value)
        
    await db.commit()
    await db.refresh(order)
    return order


@app.delete("/orders/{fiskal_doc}")
async def delete_order(
    fiskal_doc: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(auth.require_roles([models.RoleEnum.admin]))
):
    result = await db.execute(select(models.Order).filter(models.Order.fiskal_doc == fiskal_doc))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    await db.delete(order)
    await db.commit()
    return {"detail": "Заказ удален"}


@app.get("/units", response_model=List[schemas.UnitSchema])
async def get_units(db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.Unit))
    return result.scalars().all()


@app.post("/units", response_model=schemas.UnitSchema)
async def create_unit(unit: schemas.UnitSchema, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    db_unit = models.Unit(**unit.model_dump())
    db.add(db_unit)
    await db.commit()
    await db.refresh(db_unit)
    return db_unit


@app.put("/units/{unit_id}", response_model=schemas.UnitSchema)
async def update_unit(unit_id: int, unit_data: schemas.UnitSchema, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.Unit).filter(models.Unit.id == unit_id))
    db_unit = result.scalar_one_or_none()
    if not db_unit:
        raise HTTPException(status_code=404, detail="Цех не найден")
    for k, v in unit_data.model_dump().items():
        setattr(db_unit, k, v)
    await db.commit()
    await db.refresh(db_unit)
    return db_unit


@app.delete("/units/{unit_id}")
async def delete_unit(unit_id: int, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.Unit).filter(models.Unit.id == unit_id))
    db_unit = result.scalar_one_or_none()
    if not db_unit:
        raise HTTPException(status_code=404, detail="Цех не найден")
    await db.delete(db_unit)
    await db.commit()
    return {"detail": "Цех удален"}


@app.get("/storage", response_model=List[schemas.StorageSchema])
async def get_storage(db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.ProductionStorage))
    return result.scalars().all()


@app.post("/storage", response_model=schemas.StorageSchema)
async def create_storage(item: schemas.StorageSchema, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    db_item = models.ProductionStorage(**item.model_dump())
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item


@app.put("/storage/{storage_id}", response_model=schemas.StorageSchema)
async def update_storage(storage_id: int, item_data: schemas.StorageSchema, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.ProductionStorage).filter(models.ProductionStorage.id == storage_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Склад не найден")
    for k, v in item_data.model_dump().items():
        setattr(db_item, k, v)
    await db.commit()
    await db.refresh(db_item)
    return db_item


@app.delete("/storage/{storage_id}")
async def delete_storage(storage_id: int, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.worker, models.RoleEnum.admin]))):
    result = await db.execute(select(models.ProductionStorage).filter(models.ProductionStorage.id == storage_id))
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(status_code=404, detail="Склад не найден")
    await db.delete(db_item)
    await db.commit()
    return {"detail": "Склад удален"}


@app.get("/analytics/spent-on-fav", response_model=List[schemas.SpentOnFavOut])
async def get_spent_on_fav(
    db: AsyncSession = Depends(get_db),
    current_client: models.Client = Depends(auth.require_roles([models.RoleEnum.user, models.RoleEnum.admin]))
):
    if current_client.status == models.RoleEnum.admin.value:
        result = await db.execute(select(models.SpentOnFav))
        return result.scalars().all()
    
    result = await db.execute(
        select(models.SpentOnFav).filter(models.SpentOnFav.client == current_client.contact_info)
    )
    return result.scalars().all()


@app.get("/admin/clients", response_model=List[schemas.ClientOut])
async def admin_get_clients(db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.admin]))):
    result = await db.execute(select(models.Client))
    return result.scalars().all()


@app.patch("/admin/clients/{contact_info}", response_model=schemas.ClientOut)
async def admin_update_client(contact_info: str, client_data: schemas.ClientUpdate, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.admin]))):
    result = await db.execute(select(models.Client).filter(models.Client.contact_info == contact_info))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    update_dict = client_data.model_dump(exclude_unset=True)
    if "password" in update_dict:
        update_dict["hashed_password"] = auth.get_password_hash(update_dict.pop("password"))
    if "status" in update_dict and update_dict["status"] is not None:
        update_dict["status"] = update_dict["status"].value
    for k, v in update_dict.items():
        setattr(client, k, v)
    await db.commit()
    await db.refresh(client)
    return client


@app.delete("/admin/clients/{contact_info}")
async def admin_delete_client(contact_info: str, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.admin]))):
    result = await db.execute(select(models.Client).filter(models.Client.contact_info == contact_info))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    await db.delete(client)
    await db.commit()
    return {"detail": "Клиент удален"}


@app.post("/admin/breads", response_model=schemas.BreadSchema)
async def admin_create_bread(bread: schemas.BreadSchema, db: AsyncSession = Depends(get_db), _=Depends(auth.require_roles([models.RoleEnum.admin]))):
    db_bread = models.Bread(**bread.model_dump())
    db.add(db_bread)
    await db.commit()
    await db.refresh(db_bread)
    return db_bread


@app.post("/admin/test-clients/seed")
async def admin_seed_test_clients(
    data: schemas.TestClientsSeed,
    _=Depends(auth.require_roles([models.RoleEnum.admin]))
):
    async with await psycopg.AsyncConnection.connect(PSYCOPG_DATABASE_URL) as aconn:
        async with aconn.cursor() as cur:
            await cur.execute("CALL test_insert_clients(%s)", (data.n,))
            await cur.execute("CALL test_update_rnd_breads()")
        await aconn.commit()
    return {"detail": f"Создано тестовых клиентов: {data.n}"}


@app.delete("/admin/test-clients")
async def admin_delete_test_clients(
    _=Depends(auth.require_roles([models.RoleEnum.admin]))
):
    async with await psycopg.AsyncConnection.connect(PSYCOPG_DATABASE_URL) as aconn:
        async with aconn.cursor() as cur:
            await cur.execute("CALL test_delete()")
        await aconn.commit()
    return {"detail": "Тестовые клиенты удалены"}


@app.get("/breads", response_model=List[schemas.BreadSchema])
async def get_breads(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Bread))
    return result.scalars().all()