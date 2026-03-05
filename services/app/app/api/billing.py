"""Billing API endpoints for Stripe subscription management."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.billing_schemas import (
    BillingOverviewResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
    SubscriptionResponse,
    UsageSummaryResponse,
)
from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.user import User
from app.services import billing_service, quota_service

logger = structlog.get_logger()

router = APIRouter(prefix="/billing")


@router.post("/checkout", response_model=CheckoutResponse, status_code=200)
@limiter.limit("5/minute")
async def create_checkout(
    request: Request,
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for upgrading to Pro.

    Returns:
        CheckoutResponse with the Stripe Checkout URL.
    """
    if settings.self_hosted:
        raise HTTPException(status_code=400, detail="Billing is disabled in self-hosted mode")

    if user.tier == "pro":
        raise HTTPException(status_code=400, detail="Already subscribed to Pro")

    url = await billing_service.create_checkout_session(
        session, user.id, body.success_url, body.cancel_url
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse, status_code=200)
@limiter.limit("5/minute")
async def create_portal(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for subscription management.

    Returns:
        PortalResponse with the portal URL.
    """
    if settings.self_hosted:
        raise HTTPException(status_code=400, detail="Billing is disabled in self-hosted mode")

    try:
        url = await billing_service.create_portal_session(session, user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None

    return PortalResponse(portal_url=url)


@router.get("/subscription", response_model=BillingOverviewResponse)
async def get_billing_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BillingOverviewResponse:
    """Get the user's subscription status and current usage.

    Returns:
        BillingOverviewResponse with subscription and usage data.
    """
    sub = await billing_service.get_subscription(session, user.id)

    subscription = SubscriptionResponse(
        plan=sub.plan if sub else user.tier,
        status=sub.status if sub else ("active" if settings.self_hosted else "inactive"),
        current_period_start=sub.current_period_start if sub else None,
        current_period_end=sub.current_period_end if sub else None,
        cancel_at_period_end=sub.cancel_at_period_end if sub else False,
    )

    # Build usage summary
    usage_today = await quota_service.get_usage_today(session, user.id)
    monthly_uploads = await quota_service.get_monthly_upload_count(session, user.id)
    course_count = await quota_service.get_course_count(session, user.id)

    is_limited = not settings.self_hosted and user.tier == "free"

    usage = UsageSummaryResponse(
        ai_calls_today=usage_today.ai_calls_count if usage_today else 0,
        ai_calls_limit=quota_service.FREE_MAX_AI_CALLS_PER_DAY if is_limited else None,
        uploads_this_month=monthly_uploads,
        uploads_limit=quota_service.FREE_MAX_UPLOADS_PER_MONTH if is_limited else None,
        courses_count=course_count,
        courses_limit=quota_service.FREE_MAX_COURSES if is_limited else None,
    )

    return BillingOverviewResponse(subscription=subscription, usage=usage)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Handle Stripe webhook events.

    Verifies the webhook signature and processes subscription events.
    """
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    webhook_secret = settings.stripe_webhook_secret.get_secret_value()
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        logger.warning("webhook_signature_invalid")
        raise HTTPException(status_code=400, detail="Invalid signature") from None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload") from None

    logger.info("webhook_received", event_type=event["type"], event_id=event["id"])

    await billing_service.handle_webhook_event(
        session, event["type"], event["data"]
    )

    return {"status": "ok"}
