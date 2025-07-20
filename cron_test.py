import requests

token = "7575422774:AAFMZyuxHZ1ArYPE-j2rf94BIC2nBuyVPqk"
chat_id = "272327626"
text = "Тестовое сообщение"

url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}"
response = requests.get(url)

print(response.status_code)
print(response.text)