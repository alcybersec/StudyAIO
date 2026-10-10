"""Pin the ChatMessage.action_json column (GL#10 quiz-builder action)."""

from sqlalchemy.dialects.postgresql import JSONB

from app.models.chat_message import ChatMessage


class TestChatMessageActionJson:
    """action_json is a nullable JSONB column."""

    def test_action_json_is_nullable_jsonb(self) -> None:
        col = ChatMessage.__table__.c.action_json
        assert isinstance(col.type, JSONB)
        assert col.nullable is True
        assert col.default is None
        assert col.server_default is None

    def test_action_json_defaults_to_none_on_new_instance(self) -> None:
        msg = ChatMessage(session_id="s", role="assistant", content="hi")
        assert msg.action_json is None
