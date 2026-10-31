"""Format retrieved chunks for the prompt."""


def format_chunks(chunks: list[dict], max_chars: int = 3200) -> str:
    out, used = [], 0
    for i, c in enumerate(chunks, 1):
        page = f", page {c['page']}" if c.get("page") else ""
        block = f"[{i}] ({c['filename']}{page})\n{c['text'].strip()}"
        if used + len(block) > max_chars:
            break
        out.append(block)
        used += len(block)
    return "\n\n".join(out)
