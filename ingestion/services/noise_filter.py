import re

from ingestion.models.slack_message import SlackMessage
from ingestion.models.thread import SlackThread


class NoiseFilter:

    IGNORED_SUBTYPES = frozenset(
        {
            "bot_message",
            "channel_join",
            "channel_leave",
            "channel_topic",
            "channel_purpose",
            "channel_name",
        }
    )

    ERROR_KEYWORDS = (
        "error",
        "exception",
        "failed",
        "failure",
        "stack trace",
        "traceback",
        "timeout",
        "500",
        "404",
        "401",
        "403",
        "nullpointer",
        "typeerror",
        "valueerror",
        "runtimeerror",
        "connection refused",
        "connection reset",
    )

    RESOLUTION_PHRASES = (
        "fixed by",
        "fixed it",
        "resolved",
        "root cause",
        "turned out to be",
        "issue was",
        "solution was",
        "worked after",
        "working now",
    )

    def is_message_noise(self, message: SlackMessage) -> bool:
        if message.is_bot:
            return True

        if message.subtype in self.IGNORED_SUBTYPES:
            return True

        if self._is_reaction_only(message.text):
            return True

        return False

    def filter_messages(
        self,
        messages: list[SlackMessage],
    ) -> list[SlackMessage]:

        return [
            message
            for message in messages
            if not self.is_message_noise(message)
        ]

    def has_useful_signal(
        self,
        thread: SlackThread,
    ) -> bool:

        text = " ".join(
            message.text
            for message in thread.messages
        ).lower()

        return (
            self._contains_code(text)
            or self._contains_error_keyword(text)
            or self._contains_resolution_phrase(text)
        )

    def _contains_code(self, text: str) -> bool:
        return "```" in text

    def _contains_error_keyword(self, text: str) -> bool:
        return any(
            keyword in text
            for keyword in self.ERROR_KEYWORDS
        )

    def _contains_resolution_phrase(self, text: str) -> bool:
        return any(
            phrase in text
            for phrase in self.RESOLUTION_PHRASES
        )

    @staticmethod
    def _is_reaction_only(text: str) -> bool:
        if not text.strip():
            return True

        # Slack emoji syntax and common emoji-only messages.
        without_colons = re.sub(r":[^:\s]+:", "", text)

        return not any(
            character.isalnum()
            for character in without_colons
        )