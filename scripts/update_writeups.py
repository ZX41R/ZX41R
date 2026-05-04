import html
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import quote

FEED_URL = "https://zx41r.github.io/feed.xml"
MAX_ITEMS = 5
MARKER_START = "<!-- LATEST:START -->"
MARKER_END = "<!-- LATEST:END -->"

FALLBACK_MARKER_START = "<!-- WRITEUPS:START -->"
FALLBACK_MARKER_END = "<!-- WRITEUPS:END -->"

SOURCE_ALIASES = {
    "NexZeroCTF": "NexZeroCTF v3",
    "NexZeroCTF V3": "NexZeroCTF v3",
}

SOURCE_COLORS = {
    "CyberDefenders": "3558FF",
    "NexZeroCTF v3": "58A6FF",
    "Research": "A371F7",
    "Writeup": "58A6FF",
    "Post": "8B949E",
    "Notes": "6E7681",
}

KIND_COLORS = {
    "writeup": "58A6FF",
    "research": "A371F7",
    "post": "8B949E",
    "notes": "6E7681",
}

DIFFICULTY_COLORS = {
    "Easy": "57F287",
    "Medium": "FEE75C",
    "Hard": "ED4245",
    "Insane": "5865F2",
}

NOISE_TERMS = {
    "writeup",
    "research",
    "notes",
    "posts",
    "post",
    "blog",
    "ctf",
}

FOCUS_KEYWORDS = [
    "Windows Internals",
    "Malware Analysis",
    "Reverse Engineering",
    "Memory Forensics",
    "Incident Response",
    "Docker layers",
    "GitHub Events",
    "Registry Persistence",
    "Process Hollowing",
    "Config Decryption",
    "Binary Analysis",
    "File Format Repair",
    "Script Deobfuscation",
    "IOC Extraction",
]


@dataclass
class FeedItem:
    title: str
    link: str
    date: str
    categories: list[str]
    meta: dict[str, str]
    content_text: str


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def clean_html(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def slug_key(label):
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def extract_meta(content_html):
    meta = {}
    row_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
    cell_re = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
    strong_re = re.compile(r"<strong[^>]*>(.*?)</strong>", re.DOTALL | re.IGNORECASE)

    for row in row_re.findall(content_html):
        cells = cell_re.findall(row)
        if len(cells) < 2:
            continue

        label_html, value_html = cells[0], cells[1]
        strong = strong_re.search(label_html)
        label = clean_html(strong.group(1) if strong else label_html)
        value = clean_html(value_html)

        if label and value:
            meta[slug_key(label)] = value

    return meta


def parse_feed(xml_text):
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    items = []

    for entry in root.findall("atom:entry", ns)[:MAX_ITEMS]:
        title_raw = entry.find("atom:title", ns).text or ""
        title = html.unescape(title_raw).split("—")[0].strip()
        link = entry.find("atom:link", ns).get("href", "")
        date = (entry.find("atom:published", ns).text or "")[:10]
        content_el = entry.find("atom:content", ns)
        content_html = content_el.text if content_el is not None and content_el.text else ""
        categories = [
            c.get("term", "").strip()
            for c in entry.findall("atom:category", ns)
            if c.get("term", "").strip()
        ]

        items.append(
            FeedItem(
                title=title,
                link=link,
                date=date,
                categories=categories,
                meta=extract_meta(content_html),
                content_text=clean_html(content_html),
            )
        )

    return items


def badge(message, color="161b22", style="flat-square"):
    message = quote(message.replace("-", "--"), safe="")
    return f"https://img.shields.io/badge/{message}-{color}?style={style}"


def split_terms(value):
    if not value:
        return []
    terms = re.split(r"\s*(?:·|->|,|\||/)\s*", value)
    return [term.strip(" []") for term in terms if term.strip(" []")]


def bracket_term(value):
    match = re.search(r"\[([^\]]+)\]", value or "")
    return match.group(1).strip() if match else ""


def normalized_source(source):
    source = SOURCE_ALIASES.get(source, source)
    if source == "NexZeroCTF":
        return "NexZeroCTF v3"
    return source


def infer_kind(item):
    haystack = " ".join([item.title, *item.categories, *item.meta.values()]).lower()
    if any(term in haystack for term in ["writeup", "walkthrough", "challenge", "ctf"]):
        return "writeup"
    if any(term in haystack for term in ["research", "experiment", "feasibility", "internals"]):
        return "research"
    if any(term in haystack for term in ["notes", "log", "journal"]):
        return "notes"
    return "post"


def infer_source(item, kind):
    for key in ["platform", "event", "source", "lab", "project"]:
        if item.meta.get(key):
            return normalized_source(item.meta[key])

    title = item.title.lower()
    joined = " ".join([*item.categories, item.content_text]).lower()

    if "nexzeroctf" in joined or "nexzeroctf" in title:
        return "NexZeroCTF v3"
    if "cyberdefenders" in joined or "cyberdefenders" in title:
        return "CyberDefenders"

    return {
        "writeup": "Writeup",
        "research": "Research",
        "notes": "Notes",
    }.get(kind, "Post")


def source_color(source):
    return SOURCE_COLORS.get(source, "161b22")


def title_color(item, kind):
    difficulty = item.meta.get("difficulty", "")
    return DIFFICULTY_COLORS.get(difficulty, KIND_COLORS.get(kind, "58A6FF"))


def smart_focus(item):
    if item.meta.get("focus"):
        return split_terms(item.meta["focus"])[:3]

    focus = []

    for key in ["focus", "topic", "topics", "tags", "area", "domain"]:
        if item.meta.get(key):
            focus.extend(split_terms(item.meta[key]))

    category = item.meta.get("category", "")
    bracketed = bracket_term(category)
    if bracketed:
        focus.append(bracketed)
    elif category:
        focus.extend(split_terms(category)[:2])

    if item.meta.get("pivot_chain"):
        focus.extend(split_terms(item.meta["pivot_chain"])[:3])

    for category_term in item.categories:
        cleaned = category_term.strip()
        if cleaned.lower() not in NOISE_TERMS:
            focus.append(cleaned)

    lowered_text = item.content_text.lower()
    for keyword in FOCUS_KEYWORDS:
        if keyword.lower() in lowered_text:
            focus.append(keyword)

    deduped = []
    seen = set()
    for term in focus:
        key = term.lower()
        if key in NOISE_TERMS:
            continue
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)

    return deduped[:3] or ["analysis"]


def generate_section(items):
    lines = []
    for item in items:
        kind = infer_kind(item)
        source = infer_source(item, kind)
        focus_tags = " ".join(
            f'<img src="{badge(term, "161b22")}"/>' for term in smart_focus(item)
        )

        lines.append("<tr>")
        lines.append('<td align="left">')
        lines.append(f'<a href="{item.link}">')
        lines.append(f'<img src="{badge(item.title, title_color(item, kind))}"/>')
        lines.append("</a>")
        lines.append("</td>")
        lines.append(f'<td align="center"><img src="{badge(source, source_color(source))}"/></td>')
        lines.append(f'<td align="left">{focus_tags}</td>')
        lines.append(f'<td align="center"><sub>{item.date}</sub></td>')
        lines.append("</tr>")

    header = '<table align="center">\n<tr><th align="left">latest</th><th>source</th><th align="left">focus</th><th>date</th></tr>'
    return header + "\n" + "\n".join(lines) + "\n</table>"


def marker_pair(content):
    if MARKER_START in content and MARKER_END in content:
        return MARKER_START, MARKER_END
    return FALLBACK_MARKER_START, FALLBACK_MARKER_END


def update_readme(section_content):
    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker_start, marker_end = marker_pair(content)
    start = content.index(marker_start) + len(marker_start)
    end = content.index(marker_end)
    new_content = content[:start] + "\n" + section_content + "\n" + content[end:]

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    items = parse_feed(fetch_feed())
    if not items:
        print("No feed entries found.")
        return

    update_readme(generate_section(items))
    print(f"Updated README with {len(items)} feed entries.")


if __name__ == "__main__":
    main()
