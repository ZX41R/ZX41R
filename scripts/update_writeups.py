import html
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import quote

FEED_URL = "https://zx41r.github.io/feed.xml"
MAX_POSTS = 4
MARKER_START = "<!-- WRITEUPS:START -->"
MARKER_END = "<!-- WRITEUPS:END -->"

ACCENT_COLORS = {
    "Easy": "57F287",
    "Medium": "FEE75C",
    "Hard": "ED4245",
    "Insane": "5865F2",
}

PLATFORM_COLORS = {
    "CyberDefenders": "3558FF",
    "NexZeroCTF v3": "58A6FF",
}

PLATFORM_ALIASES = {
    "NexZeroCTF": "NexZeroCTF v3",
}

META_FIELDS = [
    "Platform",
    "Event",
    "Category",
    "Difficulty",
    "Focus",
    "Lab Link",
    "Challenge",
    "Pivot Chain",
]


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def clean_html(value):
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def extract_meta(content_html):
    meta = {}
    for field in META_FIELDS:
        m = re.search(
            rf"<strong>{field}</strong>\s*</td>\s*<td[^>]*>(.*?)</td>",
            content_html,
            re.DOTALL,
        )
        if m:
            meta[field.lower().replace(" ", "_")] = clean_html(m.group(1))
    return meta


def parse_feed(xml_text):
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entries = []
    for entry in root.findall("atom:entry", ns)[:MAX_POSTS]:
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
        meta = extract_meta(content_html)
        entries.append(
            {
                "title": title,
                "link": link,
                "date": date,
                "feed_categories": categories,
                **meta,
            }
        )
    return entries


def badge(message, color="161b22", style="flat-square"):
    message = quote(message.replace("-", "--"), safe="")
    return f"https://img.shields.io/badge/{message}-{color}?style={style}"


def platform_for(entry):
    platform = entry.get("platform") or entry.get("event") or "Writeup"
    platform = PLATFORM_ALIASES.get(platform, platform)
    if platform == "Writeup" and "NexZeroCTF" in entry.get("title", ""):
        return "NexZeroCTF v3"
    return platform


def split_tags(value):
    if not value:
        return []
    tags = re.split(r"\s*(?:·|->|,|\|)\s*", value)
    return [tag.strip(" []") for tag in tags if tag.strip(" []")]


def category_tags(value):
    bracketed = re.search(r"\[([^\]]+)\]", value or "")
    if bracketed:
        return [bracketed.group(1).strip()]
    return split_tags(value)[:1]


def focus_for(entry):
    if entry.get("focus"):
        return split_tags(entry["focus"])[:3]

    tags = category_tags(entry.get("category", ""))
    tags.extend(split_tags(entry.get("pivot_chain", ""))[:2])
    if not tags:
        tags = [
            c
            for c in entry.get("feed_categories", [])
            if c.lower() != "writeup" and not c.islower()
        ]
    return tags[:3] or ["analysis"]


def generate_section(entries):
    lines = []
    for e in entries:
        diff = e.get("difficulty", "")
        color = ACCENT_COLORS.get(diff, "58A6FF")
        platform = platform_for(e)
        platform_color = PLATFORM_COLORS.get(platform, "161b22")
        focus = focus_for(e)
        title = e.get("title", "")
        link = e.get("link", "#")
        date = e.get("date", "")

        title_badge = badge(title, color)
        platform_badge = badge(platform, platform_color)
        focus_tags = " ".join(
            f'<img src="{badge(tag, "161b22")}"/>' for tag in focus
        )

        lines.append("<tr>")
        lines.append('<td align="left">')
        lines.append(f'<a href="{link}">')
        lines.append(f'<img src="{title_badge}"/>')
        lines.append("</a>")
        lines.append("</td>")
        lines.append(f'<td align="center"><img src="{platform_badge}"/></td>')
        lines.append(f'<td align="left">{focus_tags}</td>')
        lines.append(f'<td align="center"><sub>{date}</sub></td>')
        lines.append("</tr>")

    header = '<table align="center">\n<tr><th align="left">writeup</th><th>platform</th><th align="left">focus</th><th>date</th></tr>'
    footer = "</table>"
    return header + "\n" + "\n".join(lines) + "\n" + footer


def update_readme(section_content):
    readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    start = content.index(MARKER_START) + len(MARKER_START)
    end = content.index(MARKER_END)
    new_content = content[:start] + "\n" + section_content + "\n" + content[end:]

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    xml_text = fetch_feed()
    entries = parse_feed(xml_text)
    if not entries:
        print("No entries found.")
        return
    section = generate_section(entries)
    update_readme(section)
    print(f"Updated README with {len(entries)} writeups.")


if __name__ == "__main__":
    main()
