from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User


async def get_user_by_phone(db: AsyncSession, phone_number: str) -> User | None:
    result = await db.execute(select(User).where(User.phone_number == phone_number))
    return result.scalars().first()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def create_user_or_set_otp(db: AsyncSession, phone_number: str) -> str:
    user = await get_user_by_phone(db, phone_number)

    otp = "12345"

    expire_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    if not user:
        user = User(phone_number=phone_number, otp_code=otp, otp_expire=expire_time)
        db.add(user)
    else:
        user.otp_code = otp
        user.otp_expire = expire_time

    await db.commit()
    return otp


async def clear_user_otp(db: AsyncSession, user: User):
    user.otp_code = None
    user.otp_expire = None
    await db.commit()