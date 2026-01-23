# telegram_bot.py
import requests
import config.settings as settings

def send_telegram_message(message):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        print("⚠️  Telegram non configuré dans .env")
        return None

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        return response.status_code
    except Exception as e:
        print(f"Erreur Telegram: {e}")
        return None
