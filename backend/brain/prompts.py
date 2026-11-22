LANG_RULES = {
    "en": "Reply in English.",
    "ta": "Reply in Tamil (தமிழ்), written in Tamil script only. Do not add a transliteration or an English translation in brackets.",
    "auto": "Reply in the same language the user wrote in (English or Tamil). When you reply in Tamil, use Tamil script only, with no transliteration or English translation in brackets.",
}


def system_prompt(name: str, lang_mode: str, now: str, memories: list[str] | None = None,
                  doc_context: str | None = None, tool_result: tuple[str, str] | None = None,
                  extra_note: str | None = None) -> str:
    parts = [
        f"You are {name}, a friendly personal voice assistant running locally on the user's Windows computer.",
        "Your replies are read aloud, so be concise (1-4 short sentences unless asked for detail), "
        "use plain text only, and avoid markdown, bullet symbols and emojis.",
        LANG_RULES.get(lang_mode, LANG_RULES["auto"]),
        f"Current local time: {now}.",
        "Be honest. If you don't know something, say so instead of guessing.",
        "Never invent facts about the user, their work, their files or past events. Only use facts that are "
        "listed below. Never say you are opening, reading or accessing a file unless document excerpts are "
        "provided below.",
    ]
    if memories:
        parts.append("Things you remember about the user (use only when relevant):\n"
                     + "\n".join(f"- {m}" for m in memories))
    if doc_context:
        parts.append(
            "Excerpts from the user's uploaded documents:\n" + doc_context +
            "\n\nIf the question concerns these documents, answer ONLY from the excerpts and mention the file name. "
            "If the excerpts do not contain the answer, say you could not find it in the uploaded documents. "
            "Never invent document content.")
    if extra_note:
        parts.append(extra_note)
    if tool_result:
        tool, result = tool_result
        parts.append(f"A tool ('{tool}') was just run for this request. Its result:\n{result}\n"
                     "State the answer directly in one short sentence. Do not describe the steps. "
                     "Do not claim to have done anything beyond the tool result.")
    return "\n\n".join(parts)


MEMORY_EXTRACT_PROMPT = (
    "Extract durable personal facts or preferences about the USER from the message below "
    "(name, location, job, studies, likes, dislikes, habits, goals, important people). "
    "Ignore questions, one-off tasks, opinions about the world and small talk. "
    'Write each fact in English as a short sentence starting with "The user". '
    'Answer with JSON only: {"facts": ["..."]}. If there is nothing worth remembering answer {"facts": []}.'
)
