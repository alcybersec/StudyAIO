"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, computed_field

from app.services import consent_service


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    # Required only when REGISTRATION_MODE=invite; ignored otherwise.
    #
    # Accepts either flavour: a shared code ("BETA-7F3KQ2MN", 13 chars) or the
    # raw token from an emailed invite link, which is secrets.token_urlsafe(32)
    # -- 43 characters. The old limit of 32 predates email invites and would
    # have rejected every one of them at validation, before the service ever
    # saw it. 100 leaves room without inviting a giant body.
    invite_code: str | None = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    """User login request."""

    email: EmailStr
    password: str
    totp_code: str | None = None
    # An MFA backup code, submitted *instead of* `totp_code` by a user who has
    # lost their authenticator. Consumed on use. Neither field replaces
    # `password`: a backup code stands in for the second factor only.
    # The max length is loose on purpose -- it has to hold the dashes and
    # stray spaces people type when copying a code off paper.
    backup_code: str | None = Field(default=None, max_length=64)


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


class OAuthMFARequest(BaseModel):
    """Second factor for an OAuth sign-in the callback left half-finished.

    Same two-of-one shape as `LoginRequest`: an authenticator code or a backup
    code, never a password. The first factor was the provider, and it is proved
    by the pending-MFA cookie rather than by anything in this body.
    """

    totp_code: str | None = None
    backup_code: str | None = Field(default=None, max_length=64)


class UpdateProfileRequest(BaseModel):
    """Profile update request."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    avatar_url: str | None = None


class SessionEndedResponse(BaseModel):
    """Response for an action that deliberately signs the caller out.

    The action stamped ``users.tokens_valid_from``, so the cookies the caller
    sent are already dead. ``session_ended`` lets the client tell that
    intentional sign-out apart from the 401 it would otherwise discover on its
    next request, and hand the user an explanation instead of a bare bounce.
    """

    detail: str
    session_ended: bool = True


class ConsentRequest(BaseModel):
    """Optional echo of the disclosure version the user was shown."""

    version: int | None = None


class ConsentResponse(BaseModel):
    """Result of recording AI-processing consent."""

    ai_consent_required: bool
    ai_consent_version: int


class AuthConfigResponse(BaseModel):
    """Public auth configuration response."""

    self_hosted: bool
    registration_enabled: bool
    oauth_providers: list[str]
    demo_enabled: bool = False
    # "open" | "invite" | "closed"
    registration_mode: str = "open"
    invite_required: bool = False


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
    # False for OAuth-only accounts. The client uses this to decide whether a
    # destructive action re-authenticates with a password or a typed username.
    has_password: bool = False
    # Set only on a login that spent an MFA backup code, so the user is told
    # how many they have left at the one moment they are thinking about it.
    # None on every other response, including a normal TOTP login -- the count
    # is not account state the client should be polling.
    backup_codes_remaining: int | None = None
    # Read from the user row only to derive ``ai_consent_required``; the raw
    # consent record is not part of the payload.
    ai_processing_consent_at: datetime | None = Field(default=None, exclude=True)
    ai_processing_consent_version: int | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ai_consent_required(self) -> bool:
        """True until the user has agreed to the current AI-processing disclosure."""
        return consent_service.consent_required(self)  # type: ignore[arg-type]

    model_config = {"from_attributes": True}


class AccountDeleteRequest(BaseModel):
    """Confirmation for irreversible account deletion.

    Password-based accounts re-authenticate with `password`. OAuth-only
    accounts have no password to check, so they confirm by typing their own
    username into `confirm_username`.
    """

    password: str | None = Field(default=None, max_length=128)
    confirm_username: str | None = Field(default=None, max_length=100)


class AccountDeletedResponse(BaseModel):
    """Result of deleting an account."""

    detail: str
    rows_deleted: int
