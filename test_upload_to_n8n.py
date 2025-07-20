import requests

# Укажи путь к файлу
file_path = "C:\\Docs\\tbot\\fin_track\\Финансовый_план_и_долги (9).xlsx"

# Webhook URL — убедись, что он точно соответствует твоему
n8n_url = "https://n8n-fintrack-dreamfish.amvera.io/webhook-test/upload-fin-file"

print(f"📤 Отправка файла {file_path} на {n8n_url}...")

try:
    with open(file_path, "rb") as f:
        files = {
            "file": (
                file_path,
                f,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        response = requests.post(n8n_url, files=files)
    print(f"✅ Статус ответа: {response.status_code}")
    print("📨 Ответ сервера:")
    print(response.text)
except Exception as e:
    print(f"❌ Ошибка при отправке файла: {e}")
