# AI Advent — практика работы с LLM API

Учебный репозиторий с практическими заданиями курса AI Advent.

В проекте последовательно изучается работа с большими языковыми моделями через API: от первого запроса до управления форматом ответа, контекстом и другими параметрами генерации.

## Выполненные задания

- [x] [День 1 — Первый запрос к LLM через API](day-01-first-api-request)
- [x] [День 2 — Управление форматом ответа](day-02-response-control)
- [ ] День 3

## Технологии

- Python
- [Groq API](https://console.groq.com/)
- GPT-OSS 20B
- Groq Python SDK
- python-dotenv

## Структура репозитория

```text
ai-advent-llm-api/
├── day-01-first-api-request/
│   ├── main.py
│   └── README.md
├── day-02-response-control/
│   ├── main.py
│   └── README.md
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Подготовка проекта

Клонируйте репозиторий:

```bash
git clone https://github.com/Ly41k/ai-advent-llm-api.git
cd ai-advent-llm-api
```

Создайте виртуальное окружение:

```bash
python -m venv .venv
```

Активируйте его.

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

Установите зависимости:

```bash
pip install -r requirements.txt
```

## Настройка API-ключа

Получите API-ключ в [Groq Console](https://console.groq.com/keys).

Создайте в корне репозитория файл `.env` на основе `.env.example`:

```env
GROQ_API_KEY=your_api_key_here
```

Файл `.env` содержит секретный ключ и уже добавлен в `.gitignore`. Не публикуйте его и не передавайте другим людям.

## Запуск заданий

Все команды выполняются из корня репозитория.

День 1:

```bash
python day-01-first-api-request/main.py
```

День 2:

```bash
python day-02-response-control/main.py
```

Для завершения любой программы введите:

```text
выход
```

## Цель репозитория

Каждая директория содержит отдельное практическое задание, рабочий пример и README с объяснением использованных возможностей LLM API.
