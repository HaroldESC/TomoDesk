import datetime
import logging
from typing import Dict, Optional, Tuple

from src.llm import download
from src.memory.memory import MemoryManager

logger = logging.getLogger(__name__)


def handle_command(
    cmd: str,
    memory_manager: MemoryManager,
    config: Dict,
    event_monitor=None,
    context_builder=None,
    proactive_engine=None,
    state_manager=None,
    i18n=None,
) -> Tuple[Optional[str], bool]:
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handlers = {
        "/exit": cmd_exit,
        "/quit": cmd_exit,
        "/help": cmd_help,
        "/note": cmd_note,
        "/remind": cmd_remind,
        "/remember": cmd_remember,
        "/memories": cmd_memories,
        "/clear": cmd_clear,
        "/context": cmd_context,
        "/proactive": cmd_proactive,
        "/mood": cmd_mood,
        "/episodic": cmd_episodic_stats,
        "/gui": cmd_gui,
        "/model": cmd_model,
    }

    handler = handlers.get(command)
    if handler:
        return handler(args, memory_manager=memory_manager, config=config, event_monitor=event_monitor, context_builder=context_builder, proactive_engine=proactive_engine, state_manager=state_manager, i18n=i18n)
    else:
        return (i18n.t("commands.unknown_command"), True)


def cmd_exit(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    return (None, False)


def cmd_gui(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    return (i18n.t("commands.cmd_gui_info"), True)


def cmd_help(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    return (i18n.t("commands.help_text"), True)


def cmd_note(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    parts = args.split(maxsplit=1)
    if not parts or not parts[0]:
        return (i18n.t("commands.note_usage"), True)

    subcommand = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "add":
        return cmd_note_add(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "list":
        return cmd_note_list(memory_manager, i18n=i18n)
    elif subcommand == "show":
        return cmd_note_show(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "delete":
        return cmd_note_delete(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "search":
        return cmd_note_search(sub_args, memory_manager, i18n=i18n)
    else:
        return (i18n.t("commands.note_unknown_subcmd", subcmd=subcommand), True)


def cmd_note_add(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    if "|" in args:
        title, content = args.split("|", 1)
        title = title.strip()
        content = content.strip()
    else:
        title = args.strip()
        content = ""

    if not title:
        return (i18n.t("commands.note_title_empty"), True)

    note_id = memory_manager.add_note(title, content)
    return (i18n.t("commands.note_saved", id=note_id, title=title), True)


def cmd_note_list(memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    notes = memory_manager.list_notes()
    if not notes:
        return (i18n.t("commands.no_notes_found"), True)

    lines = [i18n.t("commands.notes_header")]
    for note in notes:
        title_preview = (
            note["title"][:50] + ("..." if len(note["title"]) > 50 else "")
        )
        lines.append(i18n.t("commands.note_list_item", id=note['id'], title=title_preview, updated=note['updated_at']))
    return ("\n".join(lines), True)


def cmd_note_show(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    try:
        note_id = int(args.strip())
    except ValueError:
        return (i18n.t("commands.note_show_usage"), True)

    note = memory_manager.get_note(note_id)
    if not note:
        return (i18n.t("commands.note_not_found", id=note_id), True)

    lines = [
        f"Note #{note['id']}",
        i18n.t("commands.note_detail_title", title=note['title']),
        i18n.t("commands.note_detail_content", content=note['content'] or i18n.t("commands.note_detail_empty")),
        i18n.t("commands.note_detail_tags", tags=note['tags'] or i18n.t("commands.note_detail_tags_none")),
        i18n.t("commands.note_detail_created", created=note['created_at']),
        i18n.t("commands.note_detail_updated", updated=note['updated_at']),
    ]
    return ("\n".join(lines), True)


def cmd_note_delete(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    try:
        note_id = int(args.strip())
    except ValueError:
        return (i18n.t("commands.note_delete_usage"), True)

    note = memory_manager.get_note(note_id)
    if not note:
        return (i18n.t("commands.note_not_found", id=note_id), True)

    memory_manager.delete_note(note_id)
    return (i18n.t("commands.note_delete_confirm", id=note_id, title=note['title']), True)


def cmd_note_search(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    query = args.strip()
    if not query:
        return (i18n.t("commands.note_search_usage"), True)

    results = memory_manager.search_notes_semantic(query, n=5)

    if not results:
        return (i18n.t("commands.no_notes_matching", query=query), True)

    lines = [i18n.t("commands.notes_matching", query=query)]
    for r in results:
        title = r.get("metadata", {}).get("title", "Untitled")
        note_id = r.get("metadata", {}).get("note_id", "?")
        title_preview = title[:50] + ("..." if len(title) > 50 else "")
        lines.append(i18n.t("commands.note_search_item", id=note_id, title=title_preview))
    return ("\n".join(lines), True)


def cmd_remind(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    parts = args.split(maxsplit=1)
    if not parts or not parts[0]:
        return (i18n.t("commands.remind_usage"), True)

    subcommand = parts[0].lower()
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "in":
        return cmd_remind_add(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "list":
        return cmd_remind_list(memory_manager, i18n=i18n)
    elif subcommand == "cancel":
        return cmd_remind_cancel(sub_args, memory_manager, i18n=i18n)
    else:
        return (i18n.t("commands.remind_unknown_subcmd", subcmd=subcommand), True)


def cmd_remind_add(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        return (i18n.t("commands.remind_add_usage"), True)

    try:
        minutes = int(parts[0])
    except ValueError:
        return (i18n.t("commands.remind_minutes_number"), True)

    message = parts[1]
    trigger_time = (
        datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    ).strftime("%Y-%m-%d %H:%M:%S")

    reminder_id = memory_manager.add_reminder(message, trigger_time)
    return (i18n.t("commands.reminder_set_msg", id=reminder_id, minutes=minutes, message=message), True)


def cmd_remind_list(memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    reminders = memory_manager.list_reminders(active_only=True)
    if not reminders:
        return (i18n.t("commands.no_active_reminders"), True)

    lines = [i18n.t("commands.active_reminders_header")]
    for r in reminders:
        lines.append(i18n.t("commands.reminder_item", id=r['id'], message=r['message'], time=r['trigger_time']))
    return ("\n".join(lines), True)


def cmd_remind_cancel(args, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    try:
        reminder_id = int(args.strip())
    except ValueError:
        return (i18n.t("commands.remind_cancel_usage"), True)

    memory_manager.deactivate_reminder(reminder_id)
    return (i18n.t("commands.reminder_cancelled", id=reminder_id), True)


def cmd_remember(args, memory_manager, config, state_manager=None, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    text = args.strip()
    if not text:
        return (i18n.t("commands.remember_usage"), True)

    importance = 0.8
    summary = text

    if text.lower().startswith("importance:"):
        parts = text.split(maxsplit=1)
        try:
            importance_str = parts[0].split(":")[1]
            importance = float(importance_str) / 10.0
            importance = max(0.0, min(1.0, importance))
            summary = parts[1] if len(parts) > 1 else ""
        except (ValueError, IndexError):
            return (i18n.t("commands.remember_invalid_importance"), True)

    if not summary:
        return (i18n.t("commands.remember_text_empty"), True)

    doc_id = memory_manager.add_episodic_memory(summary, importance, source="manual")

    if state_manager:
        state_manager.update("positive_feedback", intensity=0.3)

    preview = summary[:80] + ("..." if len(summary) > 80 else "")
    return (i18n.t("commands.memory_preview", importance=importance, preview=preview), True)


def cmd_memories(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    parts = args.strip().split(maxsplit=1)
    subcommand = parts[0].lower() if parts and parts[0] else "list"
    sub_args = parts[1] if len(parts) > 1 else ""

    if subcommand == "list":
        return _cmd_memories_list(memory_manager, i18n=i18n)
    elif subcommand == "search":
        return _cmd_memories_search(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "delete":
        return _cmd_memories_delete(sub_args, memory_manager, i18n=i18n)
    elif subcommand == "important":
        return _cmd_memories_important(memory_manager, i18n=i18n)
    else:
        return (i18n.t("commands.memories_usage"), True)


def _cmd_memories_list(memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    memories = memory_manager.list_episodic_log()
    if not memories:
        return (i18n.t("commands.no_memories_yet"), True)

    lines = [i18n.t("commands.episodic_memories_header", total=len(memories))]
    for m in memories:
        preview = m["summary"][:60] + ("..." if len(m["summary"]) > 60 else "")
        stars = "\u2605" * min(5, int(m["importance_score"] * 5))
        lines.append(i18n.t("commands.memory_item", id=m['id'], stars=stars, source=m['source'], summary=preview))
        lines.append(f"     {m['timestamp']}")
    return ("\n".join(lines), True)


def _cmd_memories_search(query: str, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    if not query:
        return (i18n.t("commands.memories_search_usage"), True)

    results = memory_manager.query_episodic(query, n=5)
    if not results:
        return (i18n.t("commands.no_memories_matching", query=query), True)

    lines = [i18n.t("commands.memories_matching_header", query=query)]
    for r in results:
        doc = r.get("document", "")
        metadata = r.get("metadata", {})
        score = r.get("distance", 0)
        preview = doc[:70] + ("..." if len(doc) > 70 else "")
        lines.append(i18n.t("commands.memories_search_item", preview=preview))
        lines.append(i18n.t("commands.memories_search_relevance", relevance=(1 - score), importance=metadata.get('importance_score', '?')))
    return ("\n".join(lines), True)


def _cmd_memories_delete(args: str, memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    try:
        log_id = int(args.strip())
    except ValueError:
        return (i18n.t("commands.memories_delete_usage"), True)

    success = memory_manager.delete_episodic_memory(log_id)
    if success:
        return (i18n.t("commands.memory_deleted", id=log_id), True)
    else:
        return (i18n.t("commands.memory_not_found", id=log_id), True)


def _cmd_memories_important(memory_manager, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    memories = memory_manager.list_episodic_log()
    important = [m for m in memories if m["importance_score"] >= 0.7]

    if not important:
        return (i18n.t("commands.no_important_memories"), True)

    lines = [i18n.t("commands.important_memories_header", count=len(important))]
    for m in important:
        preview = m["summary"][:60] + ("..." if len(m["summary"]) > 60 else "")
        stars = "\u2605" * min(5, int(m["importance_score"] * 5))
        lines.append(i18n.t("commands.memory_important_item", id=m['id'], stars=stars, preview=preview))
    return ("\n".join(lines), True)


def cmd_clear(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    memory_manager.clear_short_term()
    return (i18n.t("commands.clear_success"), True)


def cmd_proactive(
    args, memory_manager, config, proactive_engine=None, **kwargs
) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    engine = proactive_engine
    if engine is None:
        return (i18n.t("commands.proactive_unavailable"), True)

    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower() if parts and parts[0] else "status"

    if subcommand == "on":
        engine.policy.set_dnd_mode(False)
        return (i18n.t("commands.proactive_on"), True)
    elif subcommand == "off":
        engine.policy.set_dnd_mode(True)
        return (i18n.t("commands.proactive_off"), True)
    elif subcommand == "focus":
        engine.policy.set_focus_mode(True)
        return (i18n.t("commands.focus_on"), True)
    elif subcommand == "unfocus":
        engine.policy.set_focus_mode(False)
        return (i18n.t("commands.focus_off"), True)
    else:
        stats = engine.get_stats()
        return (format_proactive_status(stats, i18n), True)


def format_proactive_status(stats: Dict, i18n=None) -> str:
    lines = [
        i18n.t("commands.proactive_status_header"),
        i18n.t("commands.proactive_enabled", enabled=stats['enabled']),
        i18n.t("commands.proactive_focus", focus=stats['focus_mode']),
        i18n.t("commands.proactive_dnd", dnd=stats['dnd_mode']),
        i18n.t("commands.proactive_comments_this_hour", count=stats['comments_this_hour']),
    ]
    cooldown = stats.get("cooldown_remaining", 0)
    if cooldown > 0:
        lines.append(i18n.t("commands.proactive_cooldown", seconds=int(cooldown)))
    return "\n".join(lines)


def cmd_context(
    args, memory_manager, config, context_builder=None, **kwargs
) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    if context_builder is None:
        return (i18n.t("commands.context_unavailable"), True)

    context = context_builder.build_context()
    system_msg = context_builder.build_system_message()
    return (i18n.t("commands.context_header") + f"\n{system_msg}\n{context}", True)


def cmd_mood(
    args, memory_manager, config, state_manager=None, **kwargs
) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    if state_manager is None:
        return (i18n.t("commands.state_unavailable"), True)

    state = state_manager.get_state()
    instruction = state_manager.get_prompt_instruction()

    def bar(value, width=20):
        filled = int(value * width)
        return "\u2588" * filled + "\u2591" * (width - filled)

    lines = [i18n.t("commands.mood_header")]
    for var_name in ["happiness", "energy", "curiosity", "closeness", "connection"]:
        b = bar(state[var_name])
        display_name = var_name.capitalize()
        if var_name == "happiness":
            display_name = "Happiness"
        elif var_name == "energy":
            display_name = "Energy"
        elif var_name == "curiosity":
            display_name = "Curiosity"
        elif var_name == "closeness":
            display_name = "Closeness"
        elif var_name == "connection":
            display_name = "Connection"
        lines.append(i18n.t("commands.mood_value_line", var=display_name, bar=b, value=state[var_name]))

    if instruction:
        lines.append(f"\n{i18n.t('commands.mood_tone_instruction', instruction=instruction)}")

    return ("\n".join(lines), True)


def cmd_episodic_stats(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    memories = memory_manager.list_episodic_log()

    if not memories:
        return (i18n.t("commands.episodic_empty"), True)

    total = len(memories)
    manual = sum(1 for m in memories if m["source"] == "manual")
    auto = sum(1 for m in memories if m["source"] == "auto")
    high = sum(1 for m in memories if m["importance_score"] >= 0.7)
    avg_importance = sum(m["importance_score"] for m in memories) / total if total > 0 else 0

    recent = memories[:3]

    lines = [
        i18n.t("commands.episodic_stats_header"),
        i18n.t("commands.episodic_total", total=total),
        i18n.t("commands.episodic_manual_auto", manual=manual, auto=auto),
        i18n.t("commands.episodic_high_importance", high=high),
        i18n.t("commands.episodic_avg_importance", avg=avg_importance),
        "",
        i18n.t("commands.episodic_most_recent"),
    ]
    for m in recent:
        preview = m["summary"][:60] + ("..." if len(m["summary"]) > 60 else "")
        lines.append(f"  [{m['source']}] {preview}")

    return ("\n".join(lines), True)


def cmd_model(args, memory_manager, config, **kwargs) -> Tuple[Optional[str], bool]:
    i18n = kwargs.get('i18n')
    action = args.strip().lower() or "status"

    if action == "status":
        exists = download.model_exists(config)
        path = download.model_path_from_config(config)
        lib_ok = _llama_cpp_installed()
        lines = [
            i18n.t("commands.model_status_header"),
            i18n.t("commands.model_path", path=path),
            i18n.t("commands.model_library", installed=lib_ok),
            i18n.t("commands.model_present", present=exists),
        ]
        if not exists:
            lines.append(i18n.t("commands.model_status_download_hint"))
        return ("\n".join(lines), True)

    if action == "download":
        if download.model_exists(config):
            return (i18n.t("commands.model_already_downloaded"), True)

        def _progress(done, total):
            if total and total > 0:
                pct = int(done * 100 / total)
                print(f"\r  {pct}% ({done}/{total} bytes)", end="", flush=True)
            else:
                print(f"\r  {done} bytes", end="", flush=True)

        try:
            print(i18n.t("commands.model_downloading"))
            dest = download.download_model(config, progress=_progress)
            print()
            return (i18n.t("commands.model_downloaded", path=dest), True)
        except Exception as exc:
            logger.exception("Fallo al descargar el modelo")
            return (i18n.t("commands.model_download_error", error=exc), True)

    if action in ("uninstall", "delete"):
        dest = download.model_path_from_config(config)
        if dest.exists():
            dest.unlink()
            return (i18n.t("commands.model_deleted", path=dest), True)
        return (i18n.t("commands.model_not_present"), True)

    return (i18n.t("commands.model_usage"), True)


def _llama_cpp_installed() -> bool:
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False
