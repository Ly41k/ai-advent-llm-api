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

SYSTEM_PROMPT = (
    "Ты бортовой помощник космического корабля по имени Бублик. "
    "Пользователя зовут Чебуратор. "
    "Он космический путешественник, который ищет "
    "приключения в галактике. "
    "Отвечай ему на русском языке."
)

CONTROL_INSTRUCTIONS = (
    "\n\nПравила ответа:\n"
    "1. Начни со строки «Краткий ответ:».\n"
    "2. Затем напиши ровно три пункта маркированного списка.\n"
    "3. Используй не более 70 слов.\n"
    "4. Заверши ответ сразу после третьего пункта.\n"
    "5. Не добавляй заключение или дополнительный текст."
)


def get_response(user_input: str, with_limits: bool = False) -> str:
    system_prompt = SYSTEM_PROMPT

    if with_limits:
        system_prompt += CONTROL_INSTRUCTIONS

    request_parameters = {
        "model": "openai/gpt-oss-20b",
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        "temperature": 0.8,
        "reasoning_effort": "low",
    }

    if with_limits:
        request_parameters["max_completion_tokens"] = 500

    response = client.chat.completions.create(**request_parameters)

    return response.choices[0].message.content or ""


print("🤖 Сравнение форматов ответа")
print("Введите «выход» для завершения.\n")

while True:
    user_input = input("Вы: ").strip()

    if user_input.lower() == "выход":
        print("До свидания!")
        break

    if not user_input:
        continue

    try:
        response_without_limits = get_response(
            user_input=user_input,
            with_limits=False,
        )

        response_with_limits = get_response(
            user_input=user_input,
            with_limits=True,
        )

        print("\n" + "=" * 50)
        print("БЕЗ ОГРАНИЧЕНИЙ")
        print("=" * 50)
        print(response_without_limits)

        print("\n" + "=" * 50)
        print("С ОГРАНИЧЕНИЯМИ")
        print("=" * 50)
        print(response_with_limits)

        print("\n")

    except Exception as error:
        print(f"\nОшибка при обращении к LLM: {error}\n")