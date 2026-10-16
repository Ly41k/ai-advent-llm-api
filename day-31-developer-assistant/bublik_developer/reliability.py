"""Bounded public recovery advice; never replay inference or restart services."""
from .errors import ErrorCode


def failure_advice(code, language="ru", *, uncertain=False):
    ru = language == "ru"
    try:
        code = ErrorCode(code)
    except ValueError:
        return None
    if code == ErrorCode.MODEL_SESSION_BUSY:
        action = "wait_for_current_request"
        text = "Сессия занята. Дождитесь текущего запроса и проверьте models status." if ru else "The session is busy. Wait for the current request and check models status."
    elif uncertain or code in {ErrorCode.MODEL_SESSION_REQUIRED, ErrorCode.MODEL_EPOCH_CHANGED}:
        action = "inspect_model_session"
        text = ("Проверьте models status. При uncertain/prepared нужен новый процесс Ollama и models confirm; автоматического повтора нет."
                if ru else "Check models status. An uncertain/prepared session needs a fresh Ollama process and models confirm; there is no automatic replay.")
    elif code in {ErrorCode.INDEX_STALE, ErrorCode.INDEX_UNAVAILABLE}:
        action = "verify_or_rebuild_index"
        text = "Проверьте индекс; при устаревших источниках пересоберите его явно." if ru else "Verify the index; rebuild explicitly if sources changed."
    elif code == ErrorCode.INVALID_MODEL_OUTPUT:
        action = "inspect_validation_reason"
        text = "Ответ модели отклонён. Проверьте output_validation_reason; автоматического повтора нет." if ru else "The model output was rejected. Check output_validation_reason; there is no automatic replay."
    elif code in {ErrorCode.PERMISSION_DENIED, ErrorCode.INVALID_INPUT, ErrorCode.WORKSPACE_CHANGED}:
        action = "correct_scope_or_input"
        text = "Проверьте запрос, права и разрешённый проект; ограничения не обходятся." if ru else "Check the request, permissions and allowed project; restrictions are not bypassed."
    elif code == ErrorCode.STATE_UNAVAILABLE:
        action = "check_private_state"
        text = "Не удалось сохранить trace. Проверьте приватный каталог состояния и свободное место." if ru else "The trace could not be saved. Check the private state directory and available space."
    else:
        action = "inspect_failure"
        text = "Операция не завершена. Проверьте diagnostics; сервисы автоматически не перезапускаются." if ru else "The operation did not complete. Check diagnostics; services are not restarted automatically."
    return {"code": code.value, "action": action, "message": text, "automatic_replay": False}
