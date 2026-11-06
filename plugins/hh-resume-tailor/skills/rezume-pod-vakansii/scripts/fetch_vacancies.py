#!/usr/bin/env python3
"""Читает вакансии hh.ru по ссылкам, которые дал пользователь, и печатает JSON.

Для каждой ссылки открывает страницу вакансии один раз (с паузой между
запросами) и достает из нее название, компанию, текст описания и ключевые
навыки, если работодатель их указал. Только стандартная библиотека Python.

Запуск:
    python3 fetch_vacancies.py https://hh.ru/vacancy/123 https://hh.ru/vacancy/456
"""
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

UA = "hh-resume-tailor/0.1 (+https://github.com/Dariap5/hh-resume-tailor)"
PAUSE = 1.5
ZW = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")


def clean(s):
    return re.sub(r"\s+", " ", ZW.sub("", s or "")).strip() or None


def vacancy_id(link):
    m = re.search(r"/vacancy/(\d+)", link) or re.fullmatch(r"\s*(\d{5,})\s*", link)
    return m.group(1) if m else None


def html_to_text(fragment):
    s = re.sub(r"<\s*(br|/p|/li|/h\d)\s*/?>", "\n", fragment, flags=re.I)
    s = re.sub(r"<\s*li[^>]*>", "- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = ZW.sub("", s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def parse(page):
    out = {"title": None, "company": None, "description": None, "key_skills": []}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            out["title"] = clean(data.get("title"))
            org = data.get("hiringOrganization") or {}
            out["company"] = clean(org.get("name")) if isinstance(org, dict) else None
            out["description"] = html_to_text(data.get("description") or "")
            break
    state = page.replace("&#34;", '"').replace("&quot;", '"')
    m = re.search(r'"keySkills":(\[[^\]]*\])', state)
    if m:
        try:
            out["key_skills"] = [html.unescape(x) for x in json.loads(m.group(1)) if isinstance(x, str)]
        except ValueError:
            pass
    return out


def fetch(link):
    vid = vacancy_id(link)
    if not vid:
        return {"link": link, "error": "не похоже на ссылку на вакансию hh.ru"}
    url = "https://hh.ru/vacancy/" + vid
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            page = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return {"link": url, "error": "hh.ru ответил кодом %d" % e.code}
    except Exception as e:  # сеть, таймаут
        return {"link": url, "error": "не удалось открыть: %s" % e}
    data = parse(page)
    data["link"] = url
    if not data["description"]:
        data["error"] = "на странице не нашлось описания вакансии (возможно, она закрыта или hh показал проверку)"
    return data


def main(args):
    if not args:
        print("Передайте одну или несколько ссылок на вакансии hh.ru", file=sys.stderr)
        return 2
    result = []
    for i, link in enumerate(args):
        if i:
            time.sleep(PAUSE)
        result.append(fetch(link))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
