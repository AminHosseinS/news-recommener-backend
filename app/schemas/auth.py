import re
from fastapi import Form
from pydantic import BaseModel, Field, field_validator

class Token(BaseModel):
    access_token: str
    token_type: str

class SendOTP(BaseModel):
    phone_number: str = Field(..., description="شماره موبایل کاربر (مثال: 09123456789)")

    @field_validator('phone_number')
    @classmethod
    def validate_iranian_phone(cls, v: str) -> str:
        if not re.match(r'^09\d{9}$', v):
            raise ValueError('شماره موبایل نامعتبر است. فرمت صحیح: 09123456789')
        return v


class OAuth2MobileOTPRequestForm:
    """
    این کلاس جایگزین OAuth2PasswordRequestForm می‌شود تا
    در صفحه Swagger فقط فیلدهای شماره موبایل و کد تایید را نشان دهد.
    """
    def __init__(
        self,
        username: str = Form(..., description="شماره موبایل"),
        password: str = Form(..., description="کد تایید پیامک شده"),
    ):
        self.username = username
        self.password = password