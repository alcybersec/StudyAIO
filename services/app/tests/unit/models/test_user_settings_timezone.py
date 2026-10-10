"""Schema contract for user_settings.timezone (R-023 clock policy)."""

from sqlalchemy import String

from app.models.user_settings import UserSettings


def test_timezone_column_is_non_null_utc_string_64() -> None:
    col = UserSettings.__table__.c.timezone
    assert isinstance(col.type, String)
    assert col.type.length == 64
    assert not col.nullable
    assert col.default.arg(None) == "UTC" if callable(col.default.arg) else col.default.arg == "UTC"
    assert str(col.server_default.arg) == "UTC"
