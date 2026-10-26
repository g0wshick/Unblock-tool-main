from pydantic import BaseModel, ConfigDict


class SlackMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_id: str
    ts: str
    thread_ts: str | None = None

    user_id: str | None = None
    text: str = ""

    subtype: str | None = None
    is_bot: bool = False

    permalink: str | None = None

    reply_count: int = 0

    raw_message_type: str | None = None