from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.auth import SendOTP, Token, OAuth2MobileOTPRequestForm
from app.crud import crud_user
from app.core.security import create_access_token

router = APIRouter()


@router.post("/send-otp")
async def send_otp_sms(
        data: SendOTP,
        db: AsyncSession = Depends(get_db)
):
    otp_code = await crud_user.create_user_or_set_otp(db, data.phone_number)

    sms_text = f"""<#> کد تایید شما: {otp_code}"""

    print(f"SMS SENT to {data.phone_number}:\n{sms_text}")

    return {"message": "کد تایید ارسال شد"}


@router.post("/login", response_model=Token)
async def verify_otp_and_login(
    form_data: OAuth2MobileOTPRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    phone_number = form_data.username
    submitted_otp = form_data.password

    user = await crud_user.get_user_by_phone(db, phone_number=phone_number)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")

    if not user.otp_code or user.otp_code != submitted_otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="کد تایید اشتباه است")

    if user.otp_expire and user.otp_expire < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="کد تایید منقضی شده است")

    await crud_user.clear_user_otp(db, user)

    access_token = create_access_token(subject=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }