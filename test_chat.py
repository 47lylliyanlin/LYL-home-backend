import requests
import json

url = "http://localhost:8000/api/chat"
data = {"message": "你好"}

response = requests.post(url, json=data)
print("状态码:", response.status_code)
print("响应内容:", response.json())
