"""User-confirmed skill ownership, separate from installation provenance."""
from copy import deepcopy
from pathlib import Path

import directions as transactions
import journal as j
from storage import locked, now, read_json

ORIGINS = {"builtin": "Встроенные и поставляемые OpenAI", "personal": "Мои разработки", "third_party": "Других авторов", "unknown": "Источник не уточнён"}
Conflict = transactions.Conflict


def state(user, inventory, skill_id):
    item = inventory["skills"].get(skill_id)
    if item is None:
        raise ValueError("Навык не найден.")
    overlay = user.get("skills", {}).get(skill_id, {})
    overridden = bool(overlay.get("origin") and overlay.get("origin_evidence"))
    origin = overlay["origin"] if overridden else item.get("origin", "unknown")
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise ValueError("Неизвестное происхождение навыка. Прежние данные не изменены.")
    evidence = overlay["origin_evidence"] if overridden else item.get("origin_evidence")
    version = {
        "skill_id": skill_id,
        "detected": {key: item.get(key) for key in ("origin", "origin_evidence", "source")},
        "selected": {key: overlay[key] for key in ("origin", "origin_evidence") if key in overlay},
    }
    return {"origin": origin, "origin_evidence": evidence, "overridden": overridden, "revision": transactions.checksum(version)}


def change(directory, skill_id, origin, revision, reason=None):
    """Set one explicit choice; caller exports afterward, as for directions."""
    if not isinstance(skill_id, str) or not skill_id:
        raise ValueError("Выберите навык.")
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise ValueError("Выберите происхождение из предложенного списка.")
    if reason is None:
        reason = "Выбор владельца в менеджере навыков."
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 2000 or "\x00" in reason:
        raise ValueError("Укажите подтверждение владельца длиной от 1 до 2000 символов.")
    reason = reason.strip()
    directory = Path(directory)
    with locked(directory):
        transactions.recover_locked(directory)
        j.read_events(directory)
        user = read_json(directory/"user.json", {"schema": 1, "skills": {}})
        inventory = read_json(directory/"inventory.json")
        before = state(user, inventory, skill_id)
        if revision != before["revision"]:
            raise Conflict("Происхождение навыка уже изменилось. Получите свежие сведения; ваш выбор сохранён в форме.")
        if before["overridden"] and before["origin"] == origin:
            return {"saved": True, "origin": origin, "revision": before["revision"], "unchanged": True}
        updated = deepcopy(user)
        overlay = updated.setdefault("skills", {}).setdefault(skill_id, {})
        overlay["origin"] = origin
        overlay["origin_evidence"] = f"Подтверждение владельца от {now()}: {reason}"
        transactions.commit_locked(directory, user, updated, "skill_origin_changed", {
            "skill_id": skill_id, "skill_name": inventory["skills"][skill_id]["name"],
            "before_origin": before["origin"], "origin": origin, "reason": reason,
        })
        return {"saved": True, "origin": origin, "revision": state(updated, inventory, skill_id)["revision"]}
