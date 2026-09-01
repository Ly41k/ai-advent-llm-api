import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError(
        "Переменная GROQ_API_KEY не найдена. "
        "Добавьте API-ключ в файл .env"
    )

client = Groq(api_key=api_key)

messages = [
    {
        "role": "system",
        "content": (
            "Ты бортовой помощник космического корабля по имени Бублик. "
            "Пользователя зовут Чебуратор. "
            "Он космический путешественник, который ищет "
            "приключения в галактике. "
            "Отвечай ему на русском языке."
        ),
    }
]

print("🤖 Чат-бот на Groq")
print("Введите «выход» для завершения.\n")

while True:
    user_input = input("Вы: ").strip()

    if user_input.lower() == "выход":
        print("До свидания!")
        break

    if not user_input:
        continue

    messages.append(
        {
            "role": "user",
            "content": user_input,
        }
    )

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.8,
            reasoning_effort="medium",
        )

        bot_response = response.choices[0].message.content or ""

        messages.append(
            {
                "role": "assistant",
                "content": bot_response,
            }
        )

        print(f"Бот: {bot_response}\n")

    except Exception as error:
        # Удаляем сообщение пользователя, на которое не получили ответ
        messages.pop()

        print(f"Ошибка при обращении к LLM: {error}\n")