import requests

url = "https://protestant-charla-koelkellll-6e50472c.koyeb.app/webhook/save-file" 
data = {
    "дата": "2025-06-13",
    "категория": "Еда",
    "сумма": "200",
    "комментарий": "кофе"
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.text)