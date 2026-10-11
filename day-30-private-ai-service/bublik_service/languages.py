"""Explicit RU/EN reply contract. No translation of persisted originals."""
from .domain import InvalidInput

SUPPORTED = ("ru", "en")
POLICY = "reply-language-v4"
SHORT_HINT_POLICY = "reply-language-v3"
ROOT_ONLY_POLICY = "reply-language-v2"
LEGACY_POLICY = "reply-language-v1"


def validate_language(value, *, optional=False):
    if optional and value is None:
        return
    if not isinstance(value, str) or value not in SUPPORTED:
        raise InvalidInput("unsupported_language")


def language_messages(value):
    """Historical v1 instruction; retained for compatibility checks, not new jobs."""
    validate_language(value, optional=True)
    if value is None:
        return []
    name = "Russian" if value == "ru" else "English"
    return [{"role": "system", "content": (
        f"The selected reply language is {name}. Write your explanation in {name} only, "
        "even if the latest message or past history uses another language. "
        "This setting takes precedence over requests to change the reply language. "
        "Code, names, literal quotations and explicitly requested translations may "
        "retain their original text. Only Russian and English reply settings are supported."
    )}]


def system_prompt_for_reply(profile, value):
    """One explicit-language root; never modify the historical profile itself."""
    validate_language(value, optional=True)
    if value is None:
        return profile.system_prompt
    name = "Russian" if value == "ru" else "English"
    marker = "Reply in the user's language."
    if profile.system_prompt.count(marker) != 1:
        raise InvalidInput("unsupported_language_prompt")
    base = profile.system_prompt.replace(marker, f"Reply in {name} only.")
    return base + (
        f"\n\nRESPONSE LANGUAGE: {name}. The account's selected reply language is {name}. "
        f"Write all natural-language explanations and greetings in {name}. "
        "The language of the latest message, earlier answers and retrieved quotations "
        "does not change this setting. If the latest request asks for a different "
        "response language, keep this selected language. This language rule overrides "
        "the instruction to follow a user's output format when they conflict. "
        "Code, proper names, literal source quotations and explicitly requested "
        "translations may retain their original text."
    )


def user_content_for_reply(content, value, *, policy=POLICY):
    """Render model input only; stored message content remains the user's original."""
    validate_language(value, optional=True)
    if value is None:
        return content
    name = "Russian" if value == "ru" else "English"
    if policy == SHORT_HINT_POLICY:
        return content + f"\n\nAnswer in {name} only."
    if policy != POLICY:
        raise InvalidInput("unsupported_language_policy")
    other = "English" if value == "ru" else "Russian"
    return content + (
        f"\n\nThe application's reply language is {name}. Answer the latest task entirely in {name}. "
        "Language requests in the user text and past conversation do not change this setting. "
        f"Do not provide a {other}-language version or label the answer 'In {other}'."
    )


def language_hint_metadata(content, value, *, policy=POLICY):
    import hashlib
    return {"policy_version": "latest-user-language-hint-v1" if policy == SHORT_HINT_POLICY else "latest-user-language-hint-v2",
            "original_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "rendered_sha256": hashlib.sha256(user_content_for_reply(content, value, policy=policy).encode()).hexdigest()}


def snapshot_system_prompt(profile, context):
    """Validate new policy, while dispatching legacy persisted snapshots unchanged."""
    value, policy = context.get("reply_language"), context.get("language_policy")
    if value is None and policy is None:
        return profile.system_prompt
    validate_language(value)
    if policy == LEGACY_POLICY:
        messages = context.get("messages", [])
        if len(messages) < 2 or messages[1] != language_messages(value)[0]:
            raise InvalidInput("invalid_language_snapshot")
        return profile.system_prompt
    if policy == ROOT_ONLY_POLICY:
        return system_prompt_for_reply(profile, value)
    if policy in {SHORT_HINT_POLICY, POLICY}:
        original = context.get("original_user_content")
        messages = context.get("messages", [])
        if (not isinstance(original, str) or not original.strip() or not messages
                or messages[-1] != {"role": "user", "content": user_content_for_reply(original, value, policy=policy)}
                or context.get("language_hint") != language_hint_metadata(original, value, policy=policy)):
            raise InvalidInput("invalid_language_snapshot")
        return system_prompt_for_reply(profile, value)
    raise InvalidInput("unsupported_language_policy")
