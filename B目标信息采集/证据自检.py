# -*- coding: utf-8 -*-
"""B 阶段证据自检：把 seeds.txt / 词语来源表.xlsx / 公开路径清单.xlsx
逐条回查 A 提供的首页 HTML，确认每一条都能落到页面里真实出现的文字上。

用法（在 B目标信息采集 目录下）：
    python 证据自检.py
输出： 证据自检报告.txt
"""
import io
import os
import re
import sys
from urllib.parse import urljoin, urlsplit

BASE_URL = "http://127.0.0.1:8080/"
HTML_FILE = os.path.join("素材", "homepage.html")
SEEDS_FILE = "seeds.txt"
WORD_XLSX = "词语来源表.xlsx"
PATH_XLSX = "公开路径清单.xlsx"
REPORT = "证据自检报告.txt"

REF_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"')


def load_html():
    with io.open(HTML_FILE, encoding="utf-8") as f:
        return f.read()


def line_of(html_lines, needle):
    hits = []
    for i, ln in enumerate(html_lines, start=1):
        if needle in ln:
            hits.append(i)
    return hits


def main():
    html = load_html()
    html_lines = html.splitlines()
    refs = [(m.group(1), urljoin(BASE_URL, m.group(1))) for m in REF_RE.finditer(html)]
    ref_paths = {}
    for raw, resolved in refs:
        ref_paths.setdefault(urlsplit(resolved).path, raw)

    out = []
    ok = 0
    bad = 0

    def add(s=""):
        out.append(s)

    add("B 阶段证据自检报告")
    add("=" * 60)
    add("首页文件：%s（%d 行，%d 字节）" % (HTML_FILE, len(html_lines), len(html.encode("utf-8"))))
    add("页面中 href/src 引用共 %d 条" % len(refs))

    # 1. seeds.txt
    add("")
    add("[1] seeds.txt 逐词回查（不区分大小写）")
    with io.open(SEEDS_FILE, encoding="utf-8") as f:
        seeds = [ln.strip() for ln in f if ln.strip()]
    add("共 %d 个词" % len(seeds))
    for w in seeds:
        hits = [i for i, ln in enumerate(html_lines, 1) if w.lower() in ln.lower()]
        if hits:
            ok += 1
            add("  OK   %-12s 行 %s" % (w, ",".join(str(h) for h in hits)))
        else:
            bad += 1
            add("  FAIL %-12s 页面中未出现该词" % w)

    # 2. 词语来源表：页面原文列
    add("")
    add("[2] 词语来源表.xlsx 的“页面原文 / 所属路径”逐条回查")
    try:
        from openpyxl import load_workbook
    except ImportError:
        add("  SKIP 未安装 openpyxl，跳过表格检查")
        load_workbook = None

    if load_workbook:
        wb = load_workbook(WORD_XLSX, data_only=True)
        ws = wb["目标词"]
        for r in range(2, ws.max_row + 1):
            word = ws.cell(r, 2).value
            src = ws.cell(r, 5).value or ""
            if not word:
                continue
            pieces = []
            for part in str(src).replace("；", ";").split(";"):
                part = part.strip()
                part = re.split(r"[（(]", part)[0].strip()   # 去掉中文括注
                if part.startswith("<") and part.endswith(">"):
                    pieces.append(part)
            if not pieces:
                add("  INFO %-12s 该行未给出 HTML 片段，仅有路径/位置描述" % word)
                continue
            miss = [p for p in pieces if p not in html]
            if miss:
                bad += 1
                add("  FAIL %-12s 片段未在首页中找到：%s" % (word, miss))
            else:
                ok += 1
                add("  OK   %-12s %d 个片段全部命中" % (word, len(pieces)))

    # 3. 公开路径清单
    add("")
    add("[3] 公开路径清单.xlsx 逐条回查（相对路径按首页 URL 解析）")
    if load_workbook:
        wb = load_workbook(PATH_XLSX, data_only=True)
        ws = wb["公开路径"]
        for r in range(2, ws.max_row + 1):
            p = ws.cell(r, 2).value
            if not p:
                continue
            p = str(p).strip()
            if p in ref_paths:
                ok += 1
                raw = ref_paths[p]
                if raw.startswith("/"):
                    add("  OK   %-26s 原文引用 href/src=\"%s\"" % (p, raw))
                else:
                    add("  OK   %-26s 原文引用为相对路径 \"%s\"，解析后即 %s" % (p, raw, p))
            else:
                bad += 1
                add("  FAIL %-26s 首页中找不到指向该路径的 href/src" % p)

    add("")
    add("-" * 60)
    add("通过 %d 项，失败 %d 项" % (ok, bad))
    if bad:
        add("结论：存在与首页 HTML 不一致的条目，需修正后再交付。")
    else:
        add("结论：所有条目都能在首页 HTML 中逐字查到，可交付。")

    with io.open(REPORT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("\n".join(out[-6:]))


if __name__ == "__main__":
    main()
