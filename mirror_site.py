"""Descarrega o site publicado (estatico) para esta pasta.

Uso (PowerShell, dentro desta pasta):
    python mirror_site.py

So usa a biblioteca padrao do Python. Segue apenas ligacoes do mesmo dominio.
"""
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://about-site-pi.vercel.app/"
OUT = os.path.dirname(os.path.abspath(__file__))
HOST = urllib.parse.urlparse(BASE).netloc

TEXT_EXT = (".html", ".htm", ".css", ".js", ".json", ".svg", ".xml", ".txt", ".webmanifest")
ASSET_EXT = TEXT_EXT + (
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico",
    ".mp4", ".webm", ".mov", ".woff", ".woff2", ".ttf", ".otf", ".pdf",
)

ATTR_RE = re.compile(r"""(?:href|src|poster|data-src)\s*=\s*["']([^"'<>]+)["']""", re.I)
SRCSET_RE = re.compile(r"""srcset\s*=\s*["']([^"']+)["']""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*["']?([^"')]+)["']?\s*\)""", re.I)
# caminhos entre aspas dentro de JavaScript, por exemplo listas de projetos
QUOTED_RE = re.compile(r"""["'`]([^"'`\s<>]+\.(?:%s))["'`]""" % "|".join(e[1:] for e in ASSET_EXT), re.I)


def normalise(url, parent):
    url = url.strip()
    if not url or url.startswith(("data:", "mailto:", "tel:", "javascript:", "#")) or "${" in url:
        return None
    full = urllib.parse.urljoin(parent, url)
    parts = urllib.parse.urlparse(full)
    if parts.scheme not in ("http", "https") or parts.netloc != HOST:
        return None
    if any(ch.isspace() for ch in parts.path):
        return None
    path = urllib.parse.quote(urllib.parse.unquote(parts.path or "/"), safe="/")
    return urllib.parse.urlunparse((parts.scheme, parts.netloc, path, "", parts.query, ""))


def local_path(url):
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    if path.endswith("/"):
        path += "index.html"
    elif not os.path.splitext(path)[1]:
        path += ".html"
    target = os.path.normpath(os.path.join(OUT, path.lstrip("/")))
    if not target.startswith(OUT):
        raise ValueError("caminho fora da pasta: " + path)
    return target


def links_in(text, parent):
    found = set()
    for rx in (ATTR_RE, CSS_URL_RE, QUOTED_RE):
        found.update(rx.findall(text))
    for group in SRCSET_RE.findall(text):
        for item in group.split(","):
            item = item.strip().split(" ")[0]
            if item:
                found.add(item)
    result = set()
    for raw in found:
        url = normalise(raw, parent)
        if url:
            result.add(url)
    return result


def main():
    queue = [BASE]
    seen = set(queue)
    ok, failed = 0, []
    while queue:
        url = queue.pop(0)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (site-backup)"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
                ctype = resp.headers.get("Content-Type", "")
        except Exception as exc:  # uma falha nao interrompe as restantes
            failed.append((url, str(exc)))
            print("FALHOU", url, exc)
            continue
        target = local_path(url)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(data)
        ok += 1
        print("ok  %9d bytes  %s" % (len(data), os.path.relpath(target, OUT)))
        is_text = target.lower().endswith(TEXT_EXT) or ctype.startswith(("text/", "application/javascript", "application/json"))
        if is_text:
            text = data.decode("utf-8", errors="replace")
            for link in sorted(links_in(text, url)):
                if link not in seen:
                    seen.add(link)
                    queue.append(link)
    print("\nDescarregados: %d ficheiros. Falhas: %d." % (ok, len(failed)))
    for url, err in failed:
        print("  -", url, "->", err)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
