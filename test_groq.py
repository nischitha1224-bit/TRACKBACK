import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "user", "content": "Reply only: TRACKBACK connected"}
        ]
    )

    print("SUCCESS:", response.choices[0].message.content)

except Exception as error:
    print("ERROR:", repr(error))