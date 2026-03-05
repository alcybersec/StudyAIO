"""Pydantic schemas for billing API endpoints."""

from datetime import datetime

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    """Request to create a Stripe Checkout session."""

    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Response with Stripe Checkout URL."""

    checkout_url: str


class PortalResponse(BaseModel):
    """Response with Stripe Customer Portal URL."""

    portal_url: str


class SubscriptionResponse(BaseModel):
    """Current subscription status."""

    plan: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class UsageSummaryResponse(BaseModel):
    """Current usage summary for the user."""

    ai_calls_today: int = 0
    ai_calls_limit: int | None = None
    uploads_this_month: int = 0
    uploads_limit: int | None = None
    courses_count: int = 0
    courses_limit: int | None = None


class BillingOverviewResponse(BaseModel):
    """Combined subscription + usage response."""

    subscription: SubscriptionResponse
    usage: UsageSummaryResponse
