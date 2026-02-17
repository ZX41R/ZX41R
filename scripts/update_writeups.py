import urllib.request
import xml.etree.ElementTree as ET
import html
import re
import os

FEED_URL = "https://zx41r.github.io/feed.xml"
MAX_POSTS = 4
MARKER_START = "<!-- WRITEUPS:START -->"
MARKER_END = "<!-- WRITEUPS:END -->"

DIFFICULTY_COLORS = {
    "Easy": "57F287",
    "Medium": "FEE75C",
    "Hard": "ED4245",
    "Insane": "5865F2",
}

DIFFICULTY_EMOJI = {
    "Easy": "🟢",
    "Medium": "🟡",
    "Hard": "🔴",
    "Insane": "🟣",
}


def fetch_feed():
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8")


def extract_meta(content_html):
    meta = {}
    for field in ["Platform", "Category", "Difficulty", "Focus", "Lab Link"]:
        m = re.search(
            rf"<strong>{field}</strong>\s*</td>\s*<td[^>]*>(.*?)</td>",
            content_html,
            re.DOTALL,
        )
        if m:
            val = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            val = html.unescape(val)
            meta[field.lower().replace(" ", "_")] = val
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
        meta = extract_meta(content_html)
        entries.append({"title": title, "link": link, "date": date, **meta})
    return entries


def generate_section(entries):
    lines = []
    for e in entries:
        diff = e.get("difficulty", "Medium")
        color = DIFFICULTY_COLORS.get(diff, "c9d1d9")
        emoji = DIFFICULTY_EMOJI.get(diff, "⚪")
        platform = e.get("platform", "Unknown")
        category = e.get("category", "")
        focus = e.get("focus", "")
        title = e.get("title", "")
        link = e.get("link", "#")
        date = e.get("date", "")

        lines.append(f'<a href="{link}">')
        lines.append(
            f'<img src="https://img.shields.io/badge/{emoji}_{title.replace(" ", "_").replace("-", "--")}-{color}?style=for-the-badge"/>'
        )
        lines.append("</a>")
        lines.append("")
        lines.append("```")
        lines.append(f"  platform   {platform}")
        lines.append(f"  category   {category}")
        lines.append(f"  difficulty {diff}")
        lines.append(f"  focus      {focus}")
        lines.append(f"  date       {date}")
        lines.append(f"  status     ██████████ ANALYZED")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


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
