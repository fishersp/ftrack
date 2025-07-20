import requests
import pandas as pd
from io import BytesIO


def get_sheet_from_drive(sheet_name: str, webhook_url: str) -> pd.DataFrame:
    """
    Получает Excel-файл с Google Drive через n8n и возвращает указанный лист как DataFrame.

    :param sheet_name: Имя листа (например: "Трекер расходов")
    :param webhook_url: URL Webhook-а n8n, например: https://n8n.example.com/webhook/get-sheet
    :return: pandas.DataFrame
    """
    try:
        response = requests.post(webhook_url)
        response.raise_for_status()
        excel_bytes = BytesIO(response.content)
        print("🔎 Тип контента:", response.headers.get("Content-Type"))
        print("📦 Размер ответа:", len(response.content))
        print("📄 Первые байты:", response.content[:100])
        df = pd.read_excel(excel_bytes, sheet_name=sheet_name, engine="openpyxl")
        return df
    except Exception as e:
        print(f"❌ Ошибка при получении данных: {e}")
        raise


# === Пример запуска ===

if __name__ == "__main__":
    # Укажи URL Webhook-а здесь:
    webhook_url = "https://n8n-fintrack-dreamfish.amvera.io/webhook-test/get-sheet"
    sheet = "Трекер расходов"

    print(f"📥 Получаем лист '{sheet}' из Excel через {webhook_url}...")
    df = get_sheet_from_drive(sheet, webhook_url)

    print("✅ Получены данные:")
    print(df.head())
