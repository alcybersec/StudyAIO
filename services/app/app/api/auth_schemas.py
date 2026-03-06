"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str
    totp_code: str | None = None


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Password reset request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Password reset with token."""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    """Email verification."""

    token: str


class MFASetupResponse(BaseModel):
    """MFA setup response with QR code and secret."""

    secret: str
    qr_code_base64: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    """MFA verification to complete setup."""

    totp_code: str = Field(min_length=6, max_length=6)
    secret: str


class MFADisableRequest(BaseModel):
    """MFA disable request."""

    totp_code: str = Field(min_length=6, max_length=6)


class MagicLinkRequest(BaseModel):
    """Magic link request."""

    email: EmailStr


class UpdateProfileRequest(BaseModel):
    """Profile update request."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    avatar_url: str | None = None


class AuthConfigResponse(BaseModel):
    """Public auth configuration response."""

    self_hosted: bool
    registration_enabled: bool
    oauth_providers: list[str]
    demo_enabled: bool = False


class UserProfileResponse(BaseModel):
    """User profile response."""

    id: str
    email: str
    username: str
    role: str
    tier: str
    is_active: bool
    email_verified: bool
    mfa_enabled: bool
    avatar_url: str | None
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
