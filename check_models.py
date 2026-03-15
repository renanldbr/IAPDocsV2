from google import genai
import os

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

for m in client.models.list():
    print(f"Model ID: {m.name}, Supported Actions: {m.supported_actions}")
