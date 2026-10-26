from slack_sdk import WebClient

from ingestion.config import get_settings


def main() -> None:
    settings = get_settings()

    client = WebClient(
        token=settings.slack_bot_token
    )

    response = client.auth_test()

    print("Authentication successful")
    print("Workspace :", response["team"])
    print("Team ID   :", response["team_id"])
    print("Bot/User  :", response["user"])
    print("User ID   :", response["user_id"])


if __name__ == "__main__":
    main()