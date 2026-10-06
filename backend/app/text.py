import html
import unicodedata

from bs4 import BeautifulSoup


def fold(text: str) -> str:
    """Loose comparison key: ignores case, Turkish dotted/dotless i and diacritics, so
    "İstanbul", "Istanbul" and "ISTANBUL" match, and "Geliştirici" matches "Gelistirici"."""
    text = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def html_to_plain(value: str) -> str:
    """Job boards return descriptions as HTML, sometimes entity-escaped HTML."""
    if not value:
        return ""
    if "&lt;" in value:
        value = html.unescape(value)
    text = BeautifulSoup(value, "html.parser").get_text("\n")
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
