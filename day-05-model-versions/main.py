# Импортируем модуль os для чтения переменных окружения.
import os

# Импортируем высокоточный таймер для измерения полного времени API-запроса.
from time import perf_counter

# Импортируем dataclass для компактного описания моделей и результатов.
from dataclasses import dataclass

# Импортируем функцию, которая загружает переменные из файла .env.
from dotenv import load_dotenv

# Импортируем основной клиент для обращения к Groq API.
from groq import Groq


# Загружаем переменные окружения из файла .env.
load_dotenv()

# Получаем API-ключ из переменной окружения GROQ_API_KEY.
api_key = os.getenv("GROQ_API_KEY")

# Проверяем, удалось ли найти API-ключ.
if not api_key:
    # Останавливаем программу и показываем понятную ошибку, если ключ отсутствует.
    raise RuntimeError(
        # Первая часть сообщения сообщает, какая переменная не найдена.
        "Переменная GROQ_API_KEY не найдена. "
        # Вторая часть сообщения объясняет, куда нужно добавить ключ.
        "Добавьте API-ключ в файл .env"
    )

# Создаём клиент Groq и передаём ему API-ключ для авторизации запросов.
client = Groq(api_key=api_key)

# Ограничиваем максимальное количество токенов одного ответа.
MAX_COMPLETION_TOKENS = 900

# Фиксируем дату, на которую были проверены публичные цены Groq.
PRICES_CHECKED_AT = "2026-09-04"

# Сохраняем ссылку на официальный список моделей и актуальные цены.
GROQ_MODELS_URL = "https://console.groq.com/docs/models"

# Создаём общий системный промпт, одинаковый для всех моделей.
SYSTEM_PROMPT = (
    # Задаём роль технического эксперта.
    "Ты Senior Kotlin Multiplatform разработчик. "
    # Требуем анализировать код практически, а не ограничиваться теорией.
    "Анализируй код точно, учитывай семантику Kotlin Coroutines и Flow. "
    # Устанавливаем язык ответа.
    "Отвечай на русском языке."
)

# Сохраняем один и тот же технический запрос для всех моделей.
TASK = """В Kotlin Multiplatform библиотеке результат Android Activity передаётся так:

private val _resultFlow = MutableSharedFlow<VeriffResult>()
val resultFlow: SharedFlow<VeriffResult> = _resultFlow.asSharedFlow()

private fun onActivityResult(result: VeriffResult) {
    _resultFlow.tryEmit(result)
}

Иногда onActivityResult() вызывается до того, как экран начинает collect resultFlow.
tryEmit() возвращает true, но экран не получает событие.

Ответь по структуре:
1. Точная причина такого поведения.
2. Минимальное исправление, которое сохранит одно событие до появления подписчика.
3. Исправленный код.
4. Сравнение replay=1, extraBufferCapacity=1 и Channel(BUFFERED).
5. Как избежать повторной обработки уже полученного результата.

Учитывай наличие нескольких подписчиков, пересоздание экрана и семантику one-time event.
Не обещай exactly-once доставку после завершения процесса приложения."""


# Описываем одну модель и необходимые данные для расчёта стоимости.
@dataclass(frozen=True)
class ModelConfig:
    # Сохраняем условный уровень модели в рамках эксперимента.
    level: str

    # Сохраняем человекочитаемое название модели.
    name: str

    # Сохраняем идентификатор, который принимает Groq API.
    model_id: str

    # Сохраняем публичную цену миллиона входных токенов в долларах.
    input_price_per_million: float

    # Сохраняем публичную цену миллиона выходных токенов в долларах.
    output_price_per_million: float

    # Сохраняем ссылку на карточку модели.
    model_url: str

    # Сохраняем минимальный режим внутренних рассуждений модели.
    reasoning_effort: str


# Описываем измеряемый результат одного API-запроса.
@dataclass(frozen=True)
class ModelResult:
    # Сохраняем конфигурацию использованной модели.
    model: ModelConfig

    # Сохраняем полный текст ответа.
    answer: str

    # Сохраняем полное время ожидания ответа в секундах.
    elapsed_seconds: float

    # Сохраняем количество входных токенов из ответа API.
    input_tokens: int

    # Сохраняем количество выходных токенов из ответа API.
    output_tokens: int

    # Сохраняем расчётную стоимость запроса в долларах.
    estimated_cost_usd: float


# Создаём три условных уровня моделей, доступных через Groq.
MODELS = (
    # Используем компактную GPT-OSS 20B как слабую модель эксперимента.
    ModelConfig(
        level="Слабая",
        name="GPT-OSS 20B",
        model_id="openai/gpt-oss-20b",
        input_price_per_million=0.075,
        output_price_per_million=0.30,
        model_url="https://huggingface.co/openai/gpt-oss-20b",
        reasoning_effort="low",
    ),
    # Используем Qwen 3.6 27B как среднюю по масштабу модель.
    ModelConfig(
        level="Средняя",
        name="Qwen 3.6 27B",
        model_id="qwen/qwen3.6-27b",
        input_price_per_million=0.60,
        output_price_per_million=3.00,
        model_url="https://huggingface.co/Qwen/Qwen3.6-27B",
        reasoning_effort="none",
    ),
    # Используем флагманскую GPT-OSS 120B как сильную модель эксперимента.
    ModelConfig(
        level="Сильная",
        name="GPT-OSS 120B",
        model_id="openai/gpt-oss-120b",
        input_price_per_million=0.15,
        output_price_per_million=0.60,
        model_url="https://huggingface.co/openai/gpt-oss-120b",
        reasoning_effort="low",
    ),
)

# Выбираем сильную модель для отдельного итогового сравнения ответов.
JUDGE_MODEL = MODELS[-1]


# Рассчитываем стоимость запроса по фактическому количеству токенов.
def calculate_cost(model: ModelConfig, input_tokens: int, output_tokens: int) -> float:
    # Рассчитываем стоимость входных токенов.
    input_cost = input_tokens / 1_000_000 * model.input_price_per_million

    # Рассчитываем стоимость выходных токенов.
    output_cost = output_tokens / 1_000_000 * model.output_price_per_million

    # Возвращаем сумму двух частей стоимости.
    return input_cost + output_cost


# Выполняем один измеряемый запрос к выбранной модели.
def get_measured_response(model: ModelConfig) -> ModelResult:
    # Запоминаем момент непосредственно перед отправкой запроса.
    started_at = perf_counter()

    # Отправляем одинаковые сообщения и параметры выбранной модели.
    response = client.chat.completions.create(
        # Передаём идентификатор текущей модели.
        model=model.model_id,
        # Передаём одинаковый системный и пользовательский промпты.
        messages=[
            # Первое сообщение определяет роль и общие правила ответа.
            {"role": "system", "content": SYSTEM_PROMPT},
            # Второе сообщение содержит одинаковое техническое задание.
            {"role": "user", "content": TASK},
        ],
        # Используем низкую температуру для более стабильного сравнения.
        temperature=0.2,
        # Используем минимальный reasoning-режим, поддерживаемый текущей моделью.
        reasoning_effort=model.reasoning_effort,
        # Устанавливаем одинаковый максимальный лимит генерации.
        max_completion_tokens=MAX_COMPLETION_TOKENS,
    )

    # Измеряем полное клиентское время после получения ответа.
    elapsed_seconds = perf_counter() - started_at

    # Получаем видимый текст ответа или пустую строку вместо None.
    answer = response.choices[0].message.content or ""

    # Не добавляем пустой ответ в итоговое сравнение.
    if not answer.strip():
        # Сообщаем, какая модель израсходовала лимит без видимого результата.
        raise RuntimeError(
            f"Модель {model.model_id} вернула пустой ответ. "
            "Сократите запрос или уменьшите reasoning effort."
        )

    # Получаем статистику токенов, рассчитанную самим API.
    usage = response.usage

    # Получаем количество входных токенов.
    input_tokens = usage.prompt_tokens

    # Получаем количество выходных токенов, включая учитываемые API токены генерации.
    output_tokens = usage.completion_tokens

    # Рассчитываем ориентировочную стоимость по публичному прайс-листу.
    estimated_cost = calculate_cost(model, input_tokens, output_tokens)

    # Возвращаем текст ответа и все измеренные показатели.
    return ModelResult(
        model=model,
        answer=answer,
        elapsed_seconds=elapsed_seconds,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost,
    )


# Выполняем отдельный запрос для автоматического сравнения качества ответов.
def get_quality_comparison(results: list[ModelResult]) -> tuple[str, int, int, float]:
    # Анонимизируем ответы, чтобы в тексте оценки не использовать размер модели как аргумент.
    anonymous_answers = "\n\n".join(
        # Подписываем каждый ответ нейтральной буквой.
        f"ОТВЕТ {chr(65 + index)}:\n{result.answer}"
        # Перебираем все результаты в исходном порядке.
        for index, result in enumerate(results)
    )

    # Подготавливаем фактические метрики под теми же анонимными обозначениями.
    anonymous_metrics = "\n".join(
        # Формируем одну строку показателей для текущей модели.
        f"{chr(65 + index)}: время {result.elapsed_seconds:.3f} с; "
        f"токены {result.input_tokens} вход + {result.output_tokens} выход; "
        f"стоимость ${result.estimated_cost_usd:.6f}"
        # Перебираем результаты в том же порядке, что и ответы.
        for index, result in enumerate(results)
    )

    # Формируем критерии проверки на основе ожидаемой семантики Flow.
    judge_prompt = (
        # Объясняем задачу оценщика.
        "Сравни три анонимных ответа на технический вопрос. "
        # Перечисляем основные критерии корректности.
        "Проверь понимание SharedFlow без подписчиков, различие replay и buffer, "
        # Добавляем требования к Channel и жизненному циклу.
        "семантику Channel при нескольких коллекторах, повторную обработку после "
        # Уточняем архитектурное ограничение гарантии доставки.
        "пересоздания и отсутствие гарантии exactly-once после смерти процесса. "
        # Требуем только короткий результат для финального блока программы.
        "Сформулируй итог из 3–5 коротких предложений. "
        # Просим охватить качество, скорость и стоимость.
        "Назови лучший ответ по качеству, самую быструю и самую дешёвую модель. "
        # Напоминаем об ограниченности одного запуска.
        "Укажи, что один запуск не является универсальным рейтингом. "
        # Запрещаем оценивать качество только по объёму текста.
        "Не используй длину ответа как самостоятельный критерий качества."
        # Передаём исходное задание оценщику.
        f"\n\nИСХОДНОЕ ЗАДАНИЕ:\n{TASK}"
        # Передаём три анонимизированных ответа.
        f"\n\nОТВЕТЫ:\n{anonymous_answers}"
        # Передаём измеренные скорость, токены и стоимость.
        f"\n\nМЕТРИКИ:\n{anonymous_metrics}"
    )

    # Отправляем запрос сильной модели с нулевой температурой.
    response = client.chat.completions.create(
        # Используем модель, выбранную для оценки.
        model=JUDGE_MODEL.model_id,
        # Передаём роль оценщика и подготовленное задание.
        messages=[
            # Системное сообщение требует строгой технической проверки.
            {
                "role": "system",
                "content": "Ты независимый эксперт по Kotlin Coroutines. Отвечай на русском языке.",
            },
            # Пользовательское сообщение содержит критерии и ответы.
            {"role": "user", "content": judge_prompt},
        ],
        # Минимизируем случайность итоговой оценки.
        temperature=0.0,
        # Ограничиваем расход токенов на внутренние рассуждения оценщика.
        reasoning_effort=JUDGE_MODEL.reasoning_effort,
        # Ограничиваем размер сравнительного ответа.
        max_completion_tokens=900,
    )

    # Получаем статистику токенов отдельного запроса-оценщика.
    usage = response.usage

    # Рассчитываем стоимость автоматической оценки отдельно от эксперимента.
    evaluation_cost = calculate_cost(
        JUDGE_MODEL,
        usage.prompt_tokens,
        usage.completion_tokens,
    )

    # Возвращаем текст оценки и показатели дополнительного запроса.
    return (
        response.choices[0].message.content or "",
        usage.prompt_tokens,
        usage.completion_tokens,
        evaluation_cost,
    )


# Печатаем один ответ вместе с его метриками.
def print_result(result: ModelResult) -> None:
    # Печатаем визуальный разделитель.
    print("\n" + "=" * 80)

    # Печатаем условный уровень, название и API-идентификатор модели.
    print(f"{result.model.level.upper()}: {result.model.name} ({result.model.model_id})")

    # Печатаем измеренные показатели одного запроса.
    print(
        f"Время: {result.elapsed_seconds:.3f} с | "
        f"Токены: {result.input_tokens} вход + {result.output_tokens} выход | "
        f"Расчётная стоимость: ${result.estimated_cost_usd:.6f}"
    )

    # Печатаем отделённый от метрик ответ модели.
    print("-" * 80)

    # Печатаем полный текст ответа.
    print(result.answer)


# Печатаем компактную итоговую таблицу измерений.
def print_metrics_table(results: list[ModelResult]) -> None:
    # Печатаем заголовок итогового раздела.
    print("\n" + "=" * 80)

    # Поясняем формат следующей таблицы.
    print("ИТОГОВЫЕ МЕТРИКИ")

    # Печатаем названия столбцов с фиксированной шириной.
    print(f"{'Модель':<22} {'Время, с':>10} {'Вход':>8} {'Выход':>8} {'Всего':>8} {'USD':>12}")

    # Печатаем разделитель таблицы.
    print("-" * 80)

    # Перебираем результаты всех трёх моделей.
    for result in results:
        # Рассчитываем общее количество токенов.
        total_tokens = result.input_tokens + result.output_tokens

        # Печатаем одну строку итоговой таблицы.
        print(
            f"{result.model.name:<22} "
            f"{result.elapsed_seconds:>10.3f} "
            f"{result.input_tokens:>8} "
            f"{result.output_tokens:>8} "
            f"{total_tokens:>8} "
            f"{result.estimated_cost_usd:>12.6f}"
        )


# Запускаем полный эксперимент пятого дня.
def main() -> None:
    # Печатаем название практического задания.
    print("🤖 День 5 — сравнение версий моделей")

    # Печатаем дату используемого прайс-листа.
    print(f"Цены проверены: {PRICES_CHECKED_AT}")

    # Печатаем ссылку, по которой можно проверить актуальные цены.
    print(f"Актуальные модели и цены: {GROQ_MODELS_URL}")

    # Печатаем исходное задание перед запуском эксперимента.
    print(f"\nОДИНАКОВЫЙ ЗАПРОС:\n{TASK}")

    # Создаём список для сохранения ответов и метрик.
    results: list[ModelResult] = []

    # Последовательно выполняем одинаковый запрос на трёх моделях.
    for model in MODELS:
        # Получаем ответ и фактические показатели текущей модели.
        result = get_measured_response(model)

        # Сохраняем результат для итоговой таблицы и оценки качества.
        results.append(result)

        # Сразу показываем ответ и его показатели.
        print_result(result)

    # Печатаем компактное сравнение скорости, токенов и стоимости.
    print_metrics_table(results)

    # Получаем отдельную автоматическую оценку качества ответов.
    quality_comparison, judge_input_tokens, judge_output_tokens, judge_cost = (
        get_quality_comparison(results)
    )

    # Показываем расход дополнительного запроса, не смешивая его с основной таблицей.
    print(
        f"\nОтдельный запрос-оценщик: {judge_input_tokens} вход + "
        f"{judge_output_tokens} выход | расчётная стоимость: ${judge_cost:.6f}"
    )

    # Поясняем ограниченность измерения ресурсоёмкости через облачный API.
    print(
        "\nПримечание: Groq API не сообщает расход GPU, RAM и энергии. "
        "В этом эксперименте ресурсоёмкость оценивается косвенно — "
        "по масштабу модели, токенам, времени и расчётной стоимости."
    )

    # Печатаем обязательный короткий вывод в самом низу результата.
    print("\n" + "=" * 80)

    # Показываем соответствие анонимных обозначений реальным моделям.
    print("КОРОТКИЙ ВЫВОД (A = GPT-OSS 20B, B = QWEN 3.6 27B, C = GPT-OSS 120B)")

    # Печатаем динамический вывод, сформированный по текущему запуску.
    print(quality_comparison)

    # Сразу после вывода печатаем ссылки на все сравниваемые модели.
    print("\nССЫЛКИ НА ВСЕ МОДЕЛИ")
    print("- GPT-OSS 20B: https://huggingface.co/openai/gpt-oss-20b")
    print("- Qwen 3.6 27B: https://huggingface.co/Qwen/Qwen3.6-27B")
    print("- GPT-OSS 120B: https://huggingface.co/openai/gpt-oss-120b")
    print("- Groq Models and Pricing: https://console.groq.com/docs/models")


# Проверяем, был ли файл запущен напрямую.
if __name__ == "__main__":
    # Начинаем общий блок обработки ошибок программы.
    try:
        # Запускаем основной эксперимент.
        main()

    # Перехватываем ошибку API или конфигурации.
    except Exception as error:
        # Показываем понятное сообщение вместо полного traceback.
        print(f"\nОшибка при выполнении эксперимента: {error}\n")
