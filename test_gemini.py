import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
try:
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents="Hello"
    )
    print("Success:", response.text)
except Exception as e:
    print("Error:", e)
