from bot.config import Settings


def main() -> None:
    settings = Settings.from_env()
    print(f"NovaAds AI ULTRA MAX configured for {len(settings.admin_ids)} admin(s).")


if __name__ == "__main__":
    main()
