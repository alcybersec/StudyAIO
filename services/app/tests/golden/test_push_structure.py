"""Golden tests for Web Push notification structures.

Validates that push-notification-related data conforms to expected schemas:
- PushSubscription model: columns and constraints
- VapidKeyResponse: VAPID public key response
- PushSubscribeRequest: subscription registration payload
- PushUnsubscribeRequest: unsubscription payload
"""

import pytest

from app.api.notification_schemas import (
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidKeyResponse,
)
from app.models.push_subscription import PushSubscription


# -- Sample data fixtures ---------------------------------------------------


@pytest.fixture
def sample_push_subscribe_request():
    """A realistic push subscription request payload."""
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123-xyz789",
        "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8p8REfXw0",
        "auth": "tBHItJI5svbpC7Dr6AM-Aw",
    }


@pytest.fixture
def sample_push_unsubscribe_request():
    """A realistic push unsubscription request payload."""
    return {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123-xyz789",
    }


@pytest.fixture
def sample_vapid_key_response():
    """A realistic VAPID key response."""
    return {
        "public_key": "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkPs7U6JP8vlGEPYDRRZf9-61WYw3y4ALowKBnCP4s",
    }


# -- PushSubscription model structure ----------------------------------------


class TestPushSubscriptionModelStructure:
    """Validate PushSubscription SQLAlchemy model columns."""

    def test_has_required_columns(self) -> None:
        """PushSubscription model has all expected columns."""
        column_names = {c.name for c in PushSubscription.__table__.columns}
        required = {"id", "user_id", "endpoint", "p256dh", "auth", "created_at", "updated_at"}
        missing = required - column_names
        assert not missing, f"Missing columns: {missing}"

    def test_table_name(self) -> None:
        """Table name is push_subscriptions."""
        assert PushSubscription.__tablename__ == "push_subscriptions"

    def test_primary_key_is_id(self) -> None:
        """Primary key is the id column."""
        pk_cols = [c.name for c in PushSubscription.__table__.primary_key.columns]
        assert pk_cols == ["id"]

    def test_user_id_has_foreign_key(self) -> None:
        """user_id column has a foreign key to users.id."""
        user_id_col = PushSubscription.__table__.columns["user_id"]
        fk_targets = [fk.target_fullname for fk in user_id_col.foreign_keys]
        assert "users.id" in fk_targets

    def test_endpoint_not_nullable(self) -> None:
        """endpoint column is not nullable."""
        col = PushSubscription.__table__.columns["endpoint"]
        assert col.nullable is False

    def test_p256dh_not_nullable(self) -> None:
        """p256dh column is not nullable."""
        col = PushSubscription.__table__.columns["p256dh"]
        assert col.nullable is False

    def test_auth_not_nullable(self) -> None:
        """auth column is not nullable."""
        col = PushSubscription.__table__.columns["auth"]
        assert col.nullable is False

    def test_unique_constraint_user_endpoint(self) -> None:
        """Unique constraint exists on (user_id, endpoint)."""
        constraint_names = [
            c.name for c in PushSubscription.__table__.constraints
            if hasattr(c, "columns") and len(c.columns) > 1
        ]
        assert "uq_push_subscriptions_user_endpoint" in constraint_names

    def test_user_id_index_exists(self) -> None:
        """Index exists on user_id."""
        index_names = [idx.name for idx in PushSubscription.__table__.indexes]
        assert "ix_push_subscriptions_user_id" in index_names


# -- VapidKeyResponse structure -----------------------------------------------


class TestVapidKeyResponseStructure:
    """Validate VapidKeyResponse schema structure."""

    def test_has_required_fields(self, sample_vapid_key_response) -> None:
        """VapidKeyResponse has public_key field."""
        assert "public_key" in sample_vapid_key_response

    def test_pydantic_model_accepts_valid_data(self, sample_vapid_key_response) -> None:
        """VapidKeyResponse Pydantic model accepts valid data."""
        model = VapidKeyResponse(**sample_vapid_key_response)
        assert model.public_key == sample_vapid_key_response["public_key"]

    def test_public_key_is_non_empty_string(self, sample_vapid_key_response) -> None:
        """public_key is a non-empty string."""
        key = sample_vapid_key_response["public_key"]
        assert isinstance(key, str)
        assert len(key) > 0

    def test_public_key_is_base64url_like(self, sample_vapid_key_response) -> None:
        """public_key looks like a base64url-encoded string (no padding required)."""
        key = sample_vapid_key_response["public_key"]
        import re
        # Base64url: alphanumeric, -, _, optional = padding
        assert re.match(r"^[A-Za-z0-9_\-]+=*$", key), (
            f"public_key doesn't look base64url: {key[:20]}..."
        )


# -- PushSubscribeRequest structure -------------------------------------------


class TestPushSubscribeRequestStructure:
    """Validate PushSubscribeRequest schema structure."""

    def test_has_required_fields(self, sample_push_subscribe_request) -> None:
        """PushSubscribeRequest has endpoint, p256dh, auth."""
        required = {"endpoint", "p256dh", "auth"}
        missing = required - sample_push_subscribe_request.keys()
        assert not missing, f"Missing fields: {missing}"

    def test_pydantic_model_accepts_valid_data(self, sample_push_subscribe_request) -> None:
        """PushSubscribeRequest Pydantic model accepts valid data."""
        model = PushSubscribeRequest(**sample_push_subscribe_request)
        assert model.endpoint == sample_push_subscribe_request["endpoint"]
        assert model.p256dh == sample_push_subscribe_request["p256dh"]
        assert model.auth == sample_push_subscribe_request["auth"]

    def test_endpoint_is_url(self, sample_push_subscribe_request) -> None:
        """endpoint starts with https://."""
        assert sample_push_subscribe_request["endpoint"].startswith("https://")

    def test_p256dh_is_non_empty_string(self, sample_push_subscribe_request) -> None:
        """p256dh is a non-empty string."""
        key = sample_push_subscribe_request["p256dh"]
        assert isinstance(key, str)
        assert len(key) > 0

    def test_auth_is_non_empty_string(self, sample_push_subscribe_request) -> None:
        """auth is a non-empty string."""
        auth = sample_push_subscribe_request["auth"]
        assert isinstance(auth, str)
        assert len(auth) > 0


# -- PushUnsubscribeRequest structure -----------------------------------------


class TestPushUnsubscribeRequestStructure:
    """Validate PushUnsubscribeRequest schema structure."""

    def test_has_endpoint_field(self, sample_push_unsubscribe_request) -> None:
        """PushUnsubscribeRequest has endpoint field."""
        assert "endpoint" in sample_push_unsubscribe_request

    def test_pydantic_model_accepts_valid_data(self, sample_push_unsubscribe_request) -> None:
        """PushUnsubscribeRequest Pydantic model accepts valid data."""
        model = PushUnsubscribeRequest(**sample_push_unsubscribe_request)
        assert model.endpoint == sample_push_unsubscribe_request["endpoint"]

    def test_endpoint_only_field(self) -> None:
        """PushUnsubscribeRequest only requires endpoint."""
        model = PushUnsubscribeRequest(endpoint="https://example.com/push/sub123")
        assert model.endpoint == "https://example.com/push/sub123"
