from pydantic import BaseModel, ConfigDict, Field

from ingestion.models.slack_message import SlackMessage


class SlackThread(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_id: str
    thread_ts: str

    root_message: SlackMessage

    messages: list[SlackMessage] = Field(default_factory=list)

    permalink: str | None = None

    contains_code: bool = False
    contains_error_keyword: bool = False
    contains_resolution_phrase: bool = False

    @property
    def message_count(self) -> int:
        return len(self.messages)