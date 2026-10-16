"""Billing service for Stripe subscription management."""

import hashlib
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.clock import utc_today
from app.core.utils import generate_id
from app.models.stripe_webhook_event import StripeWebhookEvent
from app.models.subscription import Subscription
from app.models.usage_record import UsageRecord

logger = structlog.get_logger()


def customer_fingerprint(stripe_customer_id: str | None) -> str | None:
    """Short non-reversible tag for correlating log lines; never the raw id.

    Args:
        stripe_customer_id: The Stripe customer id, or None.

    Returns:
        First 8 hex chars of its SHA-256, or None when there is no id.
    """
    if not stripe_customer_id:
        return None
    return hashlib.sha256(stripe_customer_id.encode()).hexdigest()[:8]


async def get_subscription(session: AsyncSession, user_id: str) -> Subscription | None:
    """Get a user's subscription record.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        Subscription or None if not found.
    """
    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    return result.scalar_one_or_none()


async def get_or_create_subscription(
    session: AsyncSession, user_id: str, stripe_customer_id: str
) -> Subscription:
    """Get or create a subscription record for a user.

    Args:
        session: Database session.
        user_id: The user's ID.
        stripe_customer_id: Stripe customer ID.

    Returns:
        The subscription record.
    """
    sub = await get_subscription(session, user_id)
    if sub:
        return sub

    sub = Subscription(
        id=generate_id(),
        user_id=user_id,
        stripe_customer_id=stripe_customer_id,
        plan="free",
        status="inactive",
    )
    session.add(sub)
    await session.flush()
    logger.info(
        "subscription_created",
        user_id=user_id,
        customer_fp=customer_fingerprint(stripe_customer_id),
    )
    return sub


async def create_checkout_session(
    session: AsyncSession, user_id: str, success_url: str, cancel_url: str
) -> str:
    """Create a Stripe Checkout session for upgrading to Pro.

    Args:
        session: Database session.
        user_id: The user's ID.
        success_url: URL to redirect after successful payment.
        cancel_url: URL to redirect on cancellation.

    Returns:
        The Stripe Checkout session URL.
    """
    import stripe

    stripe.api_key = settings.stripe_api_key.get_secret_value()

    # Get or create a Stripe customer
    sub = await get_subscription(session, user_id)
    if sub:
        customer_id = sub.stripe_customer_id
    else:
        customer = stripe.Customer.create(metadata={"user_id": user_id})
        customer_id = customer.id
        await get_or_create_subscription(session, user_id, customer_id)
        await session.commit()

    checkout = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
    )

    logger.info("checkout_session_created", user_id=user_id, checkout_id=checkout.id)
    return checkout.url


async def create_portal_session(session: AsyncSession, user_id: str) -> str:
    """Create a Stripe Customer Portal session for subscription management.

    Args:
        session: Database session.
        user_id: The user's ID.

    Returns:
        The Stripe Portal session URL.

    Raises:
        ValueError: If user has no subscription.
    """
    import stripe

    stripe.api_key = settings.stripe_api_key.get_secret_value()

    sub = await get_subscription(session, user_id)
    if not sub:
        raise ValueError("No subscription found for user")

    portal = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=settings.stripe_portal_return_url,
    )

    logger.info("portal_session_created", user_id=user_id)
    return portal.url


# Stripe status -> plan. Decision (R-034): ``trialing`` is a paid-for trial and
# ``past_due`` is a dunning grace period (Stripe retries the card and later
# sends ``unpaid``/``canceled`` if it fails), so both keep Pro. ``incomplete``
# (first payment not yet made) neither grants nor revokes.
PRO_STATUSES = frozenset({"active", "trialing", "past_due"})
FREE_STATUSES = frozenset({"canceled", "unpaid", "incomplete_expired", "paused"})

_SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


async def handle_webhook_event(
    session: AsyncSession,
    event_type: str,
    data: dict,
    *,
    event_id: str | None = None,
    created: int | None = None,
) -> None:
    """Process a Stripe webhook event, idempotently and in order, in Postgres.

    ``models.stripe-webhook-events v1``. The event id is claimed with an
    insert-or-skip on its unique index and the effect is applied in the same
    transaction, so a replay is a no-op, a concurrent duplicate applies once
    and a failure rolls the claim back for Stripe's retry. An event whose
    ``created`` is older than an applied one for the same customer is recorded
    ``stale`` and ignored; a per-customer advisory lock serialises the ordering
    read. An event naming no customer skips ordering.

    Args:
        session: Database session (one transaction per delivery).
        event_type: The Stripe event type.
        data: The event data object.
        event_id: The Stripe event id, for dedupe.
        created: The event's ``created`` unix timestamp, for ordering.
    """
    obj = data.get("object", {})
    if event_type not in _SUBSCRIPTION_EVENTS:
        if event_type == "checkout.session.completed":
            logger.info("checkout_completed", customer_fp=customer_fingerprint(obj.get("customer")))
        else:
            logger.debug("webhook_event_ignored", event_type=event_type)
        return

    customer = obj.get("customer")
    if not isinstance(customer, str) or not customer:
        customer = None
    created_at = datetime.fromtimestamp(created, tz=UTC) if created is not None else None

    try:
        if event_id:
            claim = await session.execute(
                pg_insert(StripeWebhookEvent)
                .values(
                    id=generate_id(),
                    stripe_event_id=event_id,
                    event_type=event_type,
                    stripe_customer_id=customer,
                    stripe_created=created_at,
                    outcome="applied",
                    created_at=datetime.now(UTC),
                )
                .on_conflict_do_nothing(index_elements=["stripe_event_id"])
                .returning(StripeWebhookEvent.id)
            )
            claim_id = claim.scalar_one_or_none()
            if claim_id is None:
                logger.info("webhook_replay_ignored", event_id=event_id, event_type=event_type)
                await session.rollback()
                return

        if created_at is not None and customer is not None:
            await session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(f"stripe:customer:{customer}", 0)
                    )
                )
            )
            newer = await session.execute(
                select(StripeWebhookEvent.id)
                .where(
                    StripeWebhookEvent.stripe_customer_id == customer,
                    StripeWebhookEvent.outcome == "applied",
                    StripeWebhookEvent.stripe_created > created_at,
                )
                .limit(1)
            )
            if newer.scalar_one_or_none() is not None:
                if event_id:
                    await session.execute(
                        update(StripeWebhookEvent)
                        .where(StripeWebhookEvent.id == claim_id)
                        .values(outcome="stale")
                    )
                await session.commit()
                logger.info(
                    "webhook_stale_ignored",
                    event_id=event_id,
                    event_type=event_type,
                    created=created,
                )
                return

        if event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(session, obj)
        else:
            await _handle_subscription_update(session, obj)
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def _handle_subscription_update(session: AsyncSession, sub_obj: dict) -> None:
    """Handle subscription created or updated events."""
    customer_id = sub_obj.get("customer")
    stripe_sub_id = sub_obj.get("id")
    status = sub_obj.get("status", "inactive")

    result = await session.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning(
            "webhook_subscription_not_found", customer_fp=customer_fingerprint(customer_id)
        )
        return

    sub.stripe_subscription_id = stripe_sub_id
    sub.status = status

    if status in PRO_STATUSES:
        sub.plan = "pro"
    elif status in FREE_STATUSES:
        sub.plan = "free"

    # Period dates
    period_start = sub_obj.get("current_period_start")
    period_end = sub_obj.get("current_period_end")
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=None)
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=None)

    sub.cancel_at_period_end = sub_obj.get("cancel_at_period_end", False)

    # Sync tier to user model
    from app.models.user import User

    user_result = await session.execute(select(User).where(User.id == sub.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.tier = sub.plan

    logger.info(
        "subscription_updated",
        user_id=sub.user_id,
        plan=sub.plan,
        status=status,
    )


async def _handle_subscription_deleted(session: AsyncSession, sub_obj: dict) -> None:
    """Handle subscription deleted event — downgrade to free."""
    customer_id = sub_obj.get("customer")

    result = await session.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning(
            "webhook_subscription_not_found", customer_fp=customer_fingerprint(customer_id)
        )
        return

    deleted_id = sub_obj.get("id")
    if deleted_id and sub.stripe_subscription_id and deleted_id != sub.stripe_subscription_id:
        # An old subscription ending must not cancel the customer's current one.
        logger.info("webhook_deleted_other_subscription_ignored", user_id=sub.user_id)
        return

    sub.plan = "free"
    sub.status = "canceled"
    sub.stripe_subscription_id = None

    # Sync tier to user model
    from app.models.user import User

    user_result = await session.execute(select(User).where(User.id == sub.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.tier = "free"

    logger.info("subscription_deleted", user_id=sub.user_id)


async def cancel_subscription(session: AsyncSession, user_id: str) -> None:
    """Cancel a user's subscription at period end.

    Args:
        session: Database session.
        user_id: The user's ID.

    Raises:
        ValueError: If no active subscription.
    """
    import stripe

    stripe.api_key = settings.stripe_api_key.get_secret_value()

    sub = await get_subscription(session, user_id)
    if not sub or not sub.stripe_subscription_id:
        raise ValueError("No active subscription to cancel")

    stripe.Subscription.modify(
        sub.stripe_subscription_id,
        cancel_at_period_end=True,
    )

    sub.cancel_at_period_end = True
    await session.commit()
    logger.info("subscription_cancel_requested", user_id=user_id)


async def record_usage(
    session: AsyncSession,
    user_id: str,
    ai_calls: int = 0,
    uploads: int = 0,
    tokens_input: int = 0,
    tokens_output: int = 0,
) -> None:
    """Record usage for quota tracking. Creates or increments today's record.

    One atomic ``INSERT ... ON CONFLICT DO UPDATE SET n = n + delta`` — the
    increment is computed by the database from the stored value. The earlier
    read-modify-write lost counts when two requests (a chat stream and an
    upload, say) updated the same day's row concurrently (COST-01).

    Args:
        session: Database session.
        user_id: The user's ID.
        ai_calls: Number of AI calls to add.
        uploads: Number of uploads to add.
        tokens_input: Input tokens to add.
        tokens_output: Output tokens to add.
    """
    now = datetime.now(UTC)
    stmt = pg_insert(UsageRecord).values(
        id=generate_id(),
        user_id=user_id,
        record_date=utc_today(),
        ai_calls_count=ai_calls,
        uploads_count=uploads,
        ai_tokens_input=tokens_input,
        ai_tokens_output=tokens_output,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_usage_user_date",
        set_={
            "ai_calls_count": UsageRecord.ai_calls_count + ai_calls,
            "uploads_count": UsageRecord.uploads_count + uploads,
            "ai_tokens_input": UsageRecord.ai_tokens_input + tokens_input,
            "ai_tokens_output": UsageRecord.ai_tokens_output + tokens_output,
            "updated_at": now,
        },
    )
    await session.execute(stmt)
    await session.flush()


def estimate_tokens(text: str = "") -> int:
    """Estimate the tokens in ``text`` (about 4 characters each).

    Used only when an adapter reports no usage. Never below
    ``ai_call_estimate_min_tokens``, which stands in for retrieved context and
    system prompts the caller cannot see.

    Args:
        text: The text sent to, or returned by, the model.

    Returns:
        The estimated token count.
    """
    return max(settings.ai_call_estimate_min_tokens, len(text) // 4)


async def record_ai_call(
    session: AsyncSession,
    user_id: str,
    agent: object | None = None,
    prompt_text: str = "",
    output_text: str = "",
) -> None:
    """Meter one request-time AI call, with tokens.

    Real token counts from the adapter win. When it reports none (the Claude
    Code CLI, streaming) an estimate is recorded instead so the global token
    ceiling still sees the spend: input is ``estimate_tokens(prompt_text)``
    (floored), output is ``len(output_text) // 4`` (at least 1).

    Best-effort: metering must never fail a request that already succeeded.
    The caller commits.

    Args:
        session: Database session.
        user_id: The owner of the work.
        agent: The AgentAdapter used, if the caller has it.
        prompt_text: What was sent, for the estimate.
        output_text: What came back, for the estimate.
    """
    try:
        usage = getattr(agent, "usage", None)
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
        if tokens_in + tokens_out == 0:
            tokens_in = estimate_tokens(prompt_text)
            tokens_out = max(1, len(output_text) // 4)
        await record_usage(
            session, user_id, ai_calls=1, tokens_input=tokens_in, tokens_output=tokens_out
        )
    except Exception:
        logger.warning("ai_call_usage_record_failed", user_id=user_id, exc_info=True)
        return
    if agent is not None and hasattr(agent, "reset_usage"):
        agent.reset_usage()


async def record_agent_usage(session: AsyncSession, user_id: str, agent: object) -> None:
    """Record what an agent consumed, then reset its counter.

    Pipeline stages call this after an AI call so the expensive bulk work shows
    up in `usage_records` — historically it did not, which left
    `*_max_ai_calls_per_day` bounding almost nothing and the token columns
    permanently empty.

    Best-effort: metering must never fail a pipeline stage that has already
    produced its output.

    Args:
        session: Database session.
        user_id: The owner of the work.
        agent: An AgentAdapter whose `usage` holds the pending consumption.
    """
    usage = getattr(agent, "usage", None)
    if usage is None or not getattr(usage, "calls", 0):
        return

    try:
        await record_usage(
            session,
            user_id,
            ai_calls=usage.calls,
            tokens_input=usage.input_tokens,
            tokens_output=usage.output_tokens,
        )
    except Exception:
        logger.warning("agent_usage_record_failed", user_id=user_id, exc_info=True)
        return

    if hasattr(agent, "reset_usage"):
        agent.reset_usage()
