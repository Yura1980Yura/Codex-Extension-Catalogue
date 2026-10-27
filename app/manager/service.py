"""A small local adapter over the existing catalogue and manual Obsidian files."""
from __future__ import annotations

from datetime import datetime
import base64
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid

import catalog as c
import directions as themes
import origins as ownership
import authors
import activation
import localization
import installation
import projects
import connections
import meshy_setup
import resources
import organization
import exporter
import journal as j
import market
from storage import atomic_json, atomic_text, locked, read_json

STATES = ("Записано", "Разбираем", "В работе", "Проверено", "Отложено")
DOCS = {"inbox": "Заметки/Наблюдения.md", "backlog": "Бэклог навыков.md", "journal": "Журнал разработки.md", "guide": "Менеджер навыков.md"}


class Conflict(ValueError):
    pass


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def clean(value, limit=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        raise ValueError("Заполните текст в допустимых пределах.")
    return value.strip()


class Manager:
    def __init__(self, data, docs, project, home, search_fn=market.search):
        self.data, self.docs, self.project, self.home = (Path(p).resolve() for p in (data, docs, project, home))
        self.search_fn = search_fn
        self.jobs = {}
        self.job_lock = threading.Lock()

    def state(self):
        for attempt in range(30):
            try:
                with locked(self.data):
                    activation_recovered = activation.recover_locked(self.data, self.home)
                    directions_recovered = themes.recover_locked(self.data)
                    inventory, cards = c.load_cards(self.data, self.project)
                    user = read_json(self.data/"user.json", {"skills": {}})
                    overlays = user["skills"]
                    direction_state = themes.state(user, inventory)
                    events = j.read_events(self.data)
                break
            except FileExistsError:
                if attempt == 29:
                    raise RuntimeError("Каталог сейчас обновляется в другом действии. Повторите открытие через несколько секунд.")
                time.sleep(.04)
        recovery = self.saved({"saved": True}) if directions_recovered or activation_recovered else {}
        visible_cards = [card for card in cards if card["state"] != "cache_only" or card["has_user_annotations"]]
        installation_facets = installation.facets(visible_cards)
        public = []
        for card in visible_cards:
            project_ids=[pid for pid,item in user.get('project_catalog',{}).get('projects',{}).items() if any(r['skill_id']==card['id'] for r in item.get('recommendations',[])) or any(r['skill_id']==card['id'] for r in item.get('applications',[]))]
            public.append({**{k: card.get(k) for k in ("id", "name", "title_ru", "origin", "author_profile", "instruction_localization", "tasks", "direction_ids", "directions", "helps", "description", "output", "state", "portability", "notes", "catalog_tags", "resource_ids", "organization_revision")}, "project_ids": project_ids, "favorite": bool(overlays.get(card["id"], {}).get("manager_favorite")), "experience_count": len(card.get("experience", [])), "installation_filter": installation_facets["skills"][card["id"]]})
        public.sort(key=lambda x: (not x["favorite"], x.get("title_ru") or x["name"]))
        curated = read_json(c.SKILL_ROOT/"assets/curation.json", {})
        proposals = {repo+":"+name: {"title": item["proposal_title_ru"], "helps": item["proposal_helps_ru"], "prepare": item.get("proposal_prepare_ru", "")} for name,item in curated.items() if item.get("proposal_title_ru") for repo in item.get("proposal_repositories", [])}
        return {"resource_summaries": resources.summaries(user), "catalog_projects": connections.project_choices(self.data), "skills": public, "installation_projects": installation_facets["projects"], "directions": direction_state["items"], "directions_revision": direction_state["revision"], "recovery_warning": recovery.get("warning"), "updated_at": inventory["updated_at"], "events": events, "wishes": self.wishes(), "documents": list(DOCS), "documentation_available": self.docs.is_dir(), "warnings": inventory.get("warnings", []), "pending_save": (self.data/"manager-pending.json").exists(), "obsidian_vault": self.docs.parents[1].name, "proposal_labels": proposals}

    def detail(self, key):
        with locked(self.data):
            activation_recovered = activation.recover_locked(self.data, self.home)
            directions_recovered = themes.recover_locked(self.data)
            card = c.show_card(self.data, key, self.project)
            direction_state = themes.state(read_json(self.data/"user.json", {"skills": {}}), read_json(self.data/"inventory.json"))
        # Only the requested skill's installation/project paths are exposed below;
        # settings, unrelated files and raw observations remain private.
        fields = ("catalog_tags", "resource_ids", "organization_revision", "id", "name", "title_ru", "origin", "origin_revision", "author_profile", "author_revision", "author_evidence", "instruction_localization", "tasks", "direction_ids", "directions", "capability_groups", "capability_limits", "helps", "description", "output", "choose_when", "prepare", "dependencies", "notes", "state", "availability", "application_allowed", "verified_experience", "historical_experience", "portability")
        result = {**{k: card.get(k) for k in fields}, "directions_revision": direction_state["revision"], "available_directions": direction_state["items"]}
        result["activation"] = activation.state(card, self.home)
        result["installation"] = installation.describe(card)
        return self.saved(result) if directions_recovered or activation_recovered else result

    def projects(self):
        with locked(self.data):
            recovered = themes.recover_locked(self.data)
            inventory, cards = c.load_cards(self.data, self.project)
            user = read_json(self.data/"user.json", {"schema": 1, "skills": {}})
            result = projects.state(user, inventory, cards, self.docs)
        return self.saved(result) if recovered else result

    def change_projects(self, data):
        try:
            return self.saved(projects.change(self.data, self.docs, self.project, data))
        except (projects.Conflict, themes.Conflict) as error:
            raise Conflict(str(error)) from error

    def connections(self, project=None):
        return connections.view(self.data, self.home, project or None)

    def resources(self, project=None):
        return resources.view(self.data, self.home, project or None)

    def change_resources(self, data):
        try:
            return self.saved(resources.change(self.data, self.home, data))
        except themes.Conflict as error:
            raise Conflict(str(error)) from error

    def change_skill_organization(self, data):
        try:
            return self.saved(organization.change_skill(self.data, data))
        except themes.Conflict as error:
            raise Conflict(str(error)) from error

    def change_connections(self, data):
        try:
            return self.saved(connections.change(self.data, self.home, data))
        except (connections.Conflict, themes.Conflict) as error:
            raise Conflict(str(error)) from error

    def probe_connection(self, key):
        return connections.probe(self.data, self.home, key)

    def meshy_status(self):
        return meshy_setup.status(self.home)

    def save_meshy_key(self, data):
        # Never route credentials through generic notes, jobs, saved results or logs.
        try:
            return meshy_setup.save_key(self.data, self.home, data.get("api_key"), data.get("revision"))
        except (ValueError, meshy_setup.vault.CredentialError):
            raise
        except Exception:
            raise ValueError("Не удалось завершить сохранение. Откройте форму заново и проверьте статус; значение ключа в ошибку не включено.") from None

    def change_activation(self, data):
        try:
            return self.saved(activation.change(self.data, self.home, self.project, data.get("id"), data.get("enabled"), data.get("revision")))
        except activation.Conflict as error:
            raise Conflict(str(error)) from error

    def change_directions(self, data):
        try:
            return self.saved(themes.change(self.data, data.get("action"), data.get("revision"), data.get("title"), data.get("direction_id"), data.get("skill_id"), data.get("ids")))
        except themes.Conflict as error:
            raise Conflict(str(error)) from error

    def change_origin(self, data):
        try:
            return self.saved(ownership.change(self.data, data.get("id"), data.get("origin"), data.get("revision")))
        except ownership.Conflict as error:
            raise Conflict(str(error)) from error

    def change_author(self, data):
        try:
            return self.saved(authors.change(self.data, data.get("id"), data.get("profile"), data.get("revision")))
        except authors.Conflict as error:
            raise Conflict(str(error)) from error

    def instruction(self, key):
        with locked(self.data):
            card = c.show_card(self.data, key, self.project)
            return localization.read(card, self.project)

    def saved(self, result):
        exported = exporter.automatic_export(self.data)
        if exported.get("warning"):
            result["warning"] = "Запись сохранена. Страницы Obsidian пока не обновились; повторите обновление, когда папка документов будет доступна."
        return result

    def note(self, key, text):
        return self.saved(c.add_note(self.data, key, clean(text)))

    def favorite(self, key, enabled):
        if not isinstance(enabled, bool):
            raise ValueError("Неверное значение избранного.")
        with locked(self.data):
            themes.recover_locked(self.data)
            j.read_events(self.data)
            if key not in read_json(self.data/"inventory.json")["skills"]:
                raise ValueError("Навык не найден.")
            user = read_json(self.data/"user.json", {"schema": 1, "skills": {}})
            overlay = user["skills"].setdefault(key, {})
            if bool(overlay.get("manager_favorite")) != enabled:
                overlay["manager_favorite"] = enabled
                atomic_json(self.data/"user.json", user)
                j.record_locked(self.data, "favorite_changed", {"skill_id": key, "favorite": enabled})
        return self.saved({"saved": True, "favorite": enabled})

    def document_path(self, name, writable=False):
        if name in DOCS:
            if writable and name not in ("inbox",):
                raise ValueError("Эта страница доступна здесь для чтения. Изменить её можно в Obsidian.")
            relative = DOCS[name]
        elif re.fullmatch(r"BK-\d{4}-\d{3,6}", name):
            if writable:
                raise ValueError("Для карточки используйте комментарий и состояние; исходная формулировка остаётся прежней.")
            relative = "Бэклог/"+name+".md"
        else:
            raise ValueError("Неизвестная заметка.")
        root = self.docs.resolve()
        path = self.docs/relative
        if not root.is_dir() or not path.resolve().is_relative_to(root) or path.is_symlink() or path.is_junction():
            raise ValueError("Папка документов недоступна или путь заметки изменён.")
        return path

    def document(self, name):
        path = self.document_path(name)
        raw = path.read_bytes()
        return {"name": name, "title": path.stem, "markdown": raw.decode("utf-8-sig"), "revision": digest(raw), "editable": name == "inbox", "obsidian_uri": self.obsidian(path)}

    def obsidian(self, path):
        from urllib.parse import urlencode
        vault = self.docs.parents[1]
        return "obsidian://open?"+urlencode({"vault": vault.name, "file": path.relative_to(vault).as_posix()})

    def save_document(self, name, text, revision):
        if not isinstance(text, str) or len(text) > 100000 or "\x00" in text:
            raise ValueError("Слишком большой или недопустимый текст.")
        path = self.document_path(name, writable=True)
        with locked(self.data):
            j.read_events(self.data)
            original = path.read_bytes()
            if digest(original) != revision:
                raise Conflict("Заметка уже изменилась в другом окне или Obsidian. Откройте свежую версию; ваш текст остался в редакторе.")
            if original.decode("utf-8-sig").replace("\r\n", "\n") == text.replace("\r\n", "\n"):
                return {"saved": True, "revision": revision, "unchanged": True}
            event = self.write_documents([(path, original, text.replace("\r\n", "\n"))], "document_saved", {"document": path.relative_to(self.docs).as_posix()})
        return self.saved({"saved": True, "revision": digest(path.read_bytes()), "event_id": event["id"]})

    def wishes(self):
        wishes = []
        for path in sorted((self.docs/"Бэклог").glob("BK-*.md"), reverse=True):
            if not re.fullmatch(r"BK-\d{4}-\d{3,6}", path.stem):
                continue
            path = self.document_path(path.stem)
            text = path.read_text("utf-8-sig")
            title = re.search(r"^# (.+)$", text, re.M)
            state = re.search(r"^- Состояние: (.+?)[.]?$", text, re.M)
            step = re.search(r"^- Следующий шаг: (.+)$", text, re.M)
            wishes.append({"id": path.stem, "title": re.sub(r"^BK-\d+-\d+\s*[—–-]\s*", "", title.group(1)) if title else path.stem, "state": state.group(1) if state else "Записано", "next_step": step.group(1) if step else "Открыть и уточнить", "revision": digest(path.read_bytes())})
        return wishes

    def create_wish(self, title, original, skill_id=None, request_id=None):
        return self.saved(self._create_wish(title, original, skill_id, request_id))

    def _create_wish(self, title, original, skill_id=None, request_id=None):
        title, original = clean(title, 140).replace("\n", " "), clean(original)
        request_fingerprint = digest(j.encoded({"title": title, "original": original, "skill_id": skill_id}))
        if request_id is not None and (not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f-]{32,36}", request_id)):
            raise ValueError("Неверный номер запроса сохранения.")
        if any(char in title for char in "|[]"):
            raise ValueError("В названии не используйте квадратные скобки и вертикальную черту.")
        with locked(self.data):
            j.read_events(self.data)
            self.recover_locked()
            if request_id:
                previous = next((e for e in j.read_events(self.data) if e["kind"] == "wish_created" and e["data"].get("request_id") == request_id), None)
                if previous:
                    if previous["data"].get("request_fingerprint") != request_fingerprint:
                        raise Conflict("Первая версия этого пожелания уже сохранена. Откройте её; изменённый текст остался в форме и может стать отдельным комментарием.")
                    return {"saved": True, "id": previous["data"]["wish_id"], "event_id": previous["id"], "resumed": True}
            index = self.document_path("backlog")
            index_original = index.read_bytes()
            index_raw = index_original.decode("utf-8-sig").replace("\r\n", "\n")
            year = datetime.now().year
            existing = [int(p.stem.rsplit("-", 1)[1]) for p in (self.docs/"Бэклог").glob(f"BK-{year}-*.md") if re.fullmatch(r"BK-\d{4}-\d{3,6}", p.stem)]
            key = f"BK-{year}-{max(existing, default=0)+1:03d}"
            path = self.document_path(key)
            related = "ещё не определены"
            if skill_id:
                cards = read_json(self.data/"inventory.json")["skills"]
                if skill_id not in cards:
                    raise ValueError("Связанный навык не найден.")
                related = f"`{cards[skill_id]['name']}`; ID `{skill_id}`"
            relative_root = self.docs.relative_to(self.docs.parents[1]).as_posix()
            date = datetime.now().strftime("%d.%m.%Y")
            body = f"# {key} — {title}\n\n- Дата: {date}.\n- Контекст: запись владельца через менеджер навыков.\n- Состояние: Записано.\n- Связанные навыки: {related}.\n- Следующий шаг: уточнить результат, когда владелец поручит работу.\n\n## Исходная формулировка\n\n"+"\n".join("> "+line for line in original.splitlines())+f"\n\n## Хронологические комментарии\n\n{date} — Сохранено пожелание. Установка и исправление этой записью не запускались.\n\n[[{relative_root}/Бэклог навыков|Вернуться в бэклог]].\n"
            row = f"| {title} | Записано | Уточнить при порученной работе | [[{relative_root}/Бэклог/{key}|{key}]] |\n"
            # Retain the owner's whole index, add only a row after its last existing table row.
            rows = list(re.finditer(r"^\|.*\|[ \t]*$", index_raw, re.M))
            if not rows:
                raise ValueError("В бэклоге не найдена таблица. Сохраните мысль в быстрые заметки или откройте Obsidian.")
            position = rows[-1].end()
            updated = index_raw[:position]+"\n"+row.rstrip("\n")+index_raw[position:]
            event = self.write_documents([(path, None, body), (index, index_original, updated)], "wish_created", {"wish_id": key, "title": title, "skill_id": skill_id, "request_id": request_id, "request_fingerprint": request_fingerprint})
        return {"saved": True, "id": key, "event_id": event["id"]}

    def update_wish(self, key, revision, state, comment, next_step=None):
        if state not in STATES:
            raise ValueError("Выберите состояние пожелания.")
        if not isinstance(comment, str) or len(comment) > 20000:
            raise ValueError("Недопустимый комментарий.")
        with locked(self.data):
            j.read_events(self.data)
            self.recover_locked()
            path = self.document_path(key)
            original = path.read_bytes()
            if digest(original) != revision:
                raise Conflict("Карточка изменилась в другом окне. Откройте её свежую версию; комментарий остаётся в форме.")
            text = original.decode("utf-8-sig").replace("\r\n", "\n")
            current = re.search(r"^- Состояние: (.+?)[.]?$", text, re.M)
            if not current:
                raise ValueError("В карточке не найдено состояние; откройте её в Obsidian.")
            if state == "Проверено" and current.group(1) != state and not comment.strip():
                raise ValueError("Для отметки «Проверено» опишите фактическую проверку или укажите отчёт.")
            step = re.search(r"^- Следующий шаг: (.+)$", text, re.M)
            if next_step is not None:
                next_step = clean(next_step, 400).replace("\n", " ")
                if any(char in next_step for char in "|[]"):
                    raise ValueError("В следующем шаге не используйте квадратные скобки и вертикальную черту.")
                if not step:
                    raise ValueError("В карточке не найден следующий шаг; откройте её в Obsidian.")
            if current.group(1) == state and not comment.strip() and (next_step is None or next_step == step.group(1)):
                return {"saved": True, "unchanged": True}
            updated = text[:current.start()]+"- Состояние: "+state+"."+text[current.end():]
            if next_step is not None:
                updated = re.sub(r"^- Следующий шаг: .+$", lambda _: "- Следующий шаг: "+next_step, updated, count=1, flags=re.M)
            if comment.strip():
                updated += "\n"+datetime.now().strftime("%d.%m.%Y %H:%M")+" — Комментарий владельца:\n\n"+"\n".join("> "+line for line in comment.strip().splitlines())+"\n"
            index = self.document_path("backlog")
            index_raw = index.read_bytes()
            index_text = index_raw.decode("utf-8-sig").replace("\r\n", "\n")
            root = self.docs.relative_to(self.docs.parents[1]).as_posix()
            rows = list(re.finditer(r"^\|.*\[\["+re.escape(root+"/Бэклог/"+key)+r"(?:\|[^\]]*)?\]\].*\|[ \t]*$", index_text, re.M))
            if len(rows) != 1:
                raise Conflict("Строка карточки в бэклоге изменилась. Сверьте её в Obsidian перед сменой состояния.")
            cells = rows[0].group().split(" | ", 3)
            if len(cells) != 4:
                raise ValueError("Формат строки бэклога изменён. Откройте его в Obsidian.")
            cells[1] = state
            if next_step is not None:
                cells[2] = next_step
            new_index = index_text[:rows[0].start()]+" | ".join(cells)+index_text[rows[0].end():]
            event = self.write_documents([(path, original, updated),(index,index_raw,new_index)], "wish_updated", {"wish_id": key, "state": state, "comment_added": bool(comment.strip())})
        return self.saved({"saved": True, "event_id": event["id"]})

    def write_documents(self, changes, kind, data):
        """Caller owns the shared lock. Save an exact forward-recovery plan first."""
        self.recover_locked()
        plan = {"schema": 1, "operation_id": uuid.uuid4().hex, "kind": kind, "data": data, "changes": []}
        for path, before, after in changes:
            if (path.read_bytes() if path.exists() else None) != before:
                raise Conflict("Документ уже изменился. Откройте свежую версию перед сохранением.")
            plan["changes"].append({"document": path.relative_to(self.docs).as_posix(), "before": digest(before) if before is not None else None, "after": digest(after.encode("utf-8")), "text": after})
            if before is not None:
                backup = self.data/"backups/manager-notes"/(digest(before)+".json")
                if not backup.exists():
                    atomic_json(backup, {"sha256": digest(before), "original_base64": base64.b64encode(before).decode()})
        plan["sha256"] = digest(j.encoded(plan))
        atomic_json(self.data/"manager-pending.json", plan)
        return self.recover_locked()

    def recover_locked(self):
        receipt = self.data/"manager-pending.json"
        if not receipt.exists():
            return None
        plan = read_json(receipt)
        if not isinstance(plan, dict) or plan.get("schema") != 1 or plan.get("sha256") != digest(j.encoded({k:v for k,v in plan.items() if k != "sha256"})):
            raise ValueError("Квитанция сохранения повреждена. Она сохранена для разбора; документы не перезаписаны.")
        changes = plan.get("changes")
        if not isinstance(changes, list) or not 1 <= len(changes) <= 2:
            raise ValueError("Неверный состав квитанции сохранения.")
        targets = []
        for change in changes:
            relative = change["document"]
            allowed = relative in (DOCS["inbox"], DOCS["backlog"]) or bool(re.fullmatch(r"Бэклог/BK-\d{4}-\d{3,6}\.md", relative))
            path = self.docs/relative
            if not allowed or not path.resolve().is_relative_to(self.docs) or path.is_symlink() or path.is_junction():
                raise ValueError("Недопустимый путь в квитанции сохранения.")
            if digest(change["text"].encode()) != change["after"]:
                raise ValueError("Контрольная сумма квитанции не совпала.")
            current = digest(path.read_bytes()) if path.exists() else None
            if current not in (change["before"], change["after"]):
                raise Conflict("После прерывания документ изменён вручную. Текст сохранения остался в manager-pending.json; сверка нужна в Obsidian.")
            targets.append((path,change,current))
        events = j.read_events(self.data)
        for path,change,current in targets:
            if current != change["after"]:
                if (digest(path.read_bytes()) if path.exists() else None) != current:
                    raise Conflict("Документ изменился во время сохранения; квитанция сохранена, чужие правки не заменены.")
                atomic_text(path, change["text"])
        event = next((event for event in events if event["data"].get("operation_id") == plan["operation_id"]), None)
        if not event:
            event = j.record_locked(self.data, plan["kind"], {**plan["data"], "operation_id": plan["operation_id"]})
        receipt.unlink()
        return event

    def recover(self):
        with locked(self.data):
            event = self.recover_locked()
        return self.saved({"saved": True, "event_id": event["id"] if event else None})

    def start_job(self, action, query=None):
        if action == "search":
            query = clean(query, 500)
        elif action != "refresh":
            raise ValueError("Неизвестное действие.")
        with self.job_lock:
            if any(job["status"] == "running" for job in self.jobs.values()):
                raise Conflict("Предыдущее действие ещё выполняется. Дождитесь его результата.")
            key = uuid.uuid4().hex
            self.jobs[key] = {"status": "running", "action": action}
        def work():
            try:
                if action == "search":
                    result = self.search_fn(self.data, query)
                else:
                    inventory = c.refresh(self.data, self.home, self.project)
                    result = {"updated_at": inventory["updated_at"], "warnings": inventory["warnings"]}
                result = self.saved(result)
                completed = {"status": "done", "action": action, "result": result}
            except Exception as error:
                self.saved({})
                completed = {"status": "error", "action": action, "error": str(error)}
            with self.job_lock:
                self.jobs[key] = completed
        threading.Thread(target=work, daemon=True).start()
        return {"job_id": key}

    def job(self, key):
        with self.job_lock:
            if key not in self.jobs:
                raise ValueError("Действие не найдено. Посмотрите сохранённую историю.")
            return dict(self.jobs[key])
