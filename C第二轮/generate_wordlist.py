#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C组第二轮候选字典生成脚本。只生成文件，不发送HTTP请求。"""

from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import re
import sys

try:
    from openpyxl import load_workbook
except ImportError:
    print("缺少 openpyxl，请执行：py -3 -m pip install openpyxl")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent
BASELINE_FILE = ROOT / "baseline_1000.txt"
SEEDS_FILE = ROOT / "seeds.txt"
SOURCE_FILE = ROOT / "词语来源表-第二轮.xlsx"

# 保留原脚本的拼写纠正规则
# 原词不会被删除，纠正后的词作为额外候选加入
SPELLING_CORRECTIONS = {
    "subdmain": ["subdomain"]
}


def read_lines(path):
    if not path.exists():
        raise FileNotFoundError("找不到输入文件：" + path.name)

    return [
        x.strip()
        for x in path.read_text(encoding="utf-8-sig").splitlines()
        if x.strip()
    ]


def allowed(value):
    value = value.strip()

    if not value or "://" in value or "?" in value or "#" in value:
        return False

    if value.startswith(("/", "\\")) or "\\" in value:
        return False

    parts = value.split("/")

    if value.endswith("/"):
        parts = parts[:-1]

    if any(p in ("", ".", "..") for p in parts):
        return False

    if any(p.lower() in ("rate", "limited") for p in parts):
        return False

    return True


def plural(word):
    if not re.fullmatch(r"[A-Za-z]+", word):
        return None

    if len(word) > 3 and word.lower().endswith("s"):
        return word[:-1]

    return word + "s"


def load_sources(path):
    if not path.exists():
        raise FileNotFoundError("找不到输入文件：" + path.name)

    wb = load_workbook(path, data_only=True)

    if "目标词" not in wb.sheetnames:
        raise ValueError("来源表中缺少“目标词”工作表")

    ws = wb["目标词"]
    headers = [c.value for c in ws[1]]
    index = {
        h: i
        for i, h in enumerate(headers)
        if h is not None
    }

    required = [
        "词语",
        "来源类别",
        "来源位置",
        "页面原文 / 所属路径",
        "提取理由",
        "截图编号"
    ]

    missing = [x for x in required if x not in index]

    if missing:
        raise ValueError("来源表缺少列：" + "、".join(missing))

    result = defaultdict(list)

    for row in ws.iter_rows(min_row=2, values_only=True):
        word = str(row[index["词语"]] or "").strip().lower()

        if not word:
            continue

        result[word].append({
            "来源类别": str(row[index["来源类别"]] or "").strip(),
            "来源位置": str(row[index["来源位置"]] or "").strip(),
            "页面原文/所属路径": str(
                row[index["页面原文 / 所属路径"]] or ""
            ).strip(),
            "提取理由": str(row[index["提取理由"]] or "").strip(),
            "截图编号": str(row[index["截图编号"]] or "").strip()
        })

    return result


def sha256(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)

    return h.hexdigest()


def write_list(path, values):
    path.write_text(
        "\n".join(values) + "\n",
        encoding="utf-8"
    )


def main():
    baseline_raw = read_lines(BASELINE_FILE)
    seeds_raw = read_lines(SEEDS_FILE)

    baseline_valid = [
        x for x in baseline_raw
        if allowed(x)
    ]

    baseline = list(dict.fromkeys(baseline_valid))
    seeds = list(dict.fromkeys(seeds_raw))

    sources = load_sources(SOURCE_FILE)

    # 第一阶段：基线 + 原始种子，只去重，不做任何扩展。
    baseline_plus = list(
        dict.fromkeys(
            baseline + [
                x for x in seeds
                if allowed(x)
            ]
        )
    )

    # 第二阶段：按原脚本顺序生成种子候选，再追加基线。
    expanded = []
    provenance = defaultdict(list)

    def add(candidate, original, category, expanded_flag, rule, infos):
        if not allowed(candidate):
            return

        if candidate not in provenance:
            expanded.append(candidate)

        source_rows = infos or [{
            "来源类别": category,
            "来源位置": "",
            "页面原文/所属路径": "",
            "提取理由": "",
            "截图编号": ""
        }]

        for info in source_rows:
            record = {
                "候选": candidate,
                "原始词": original,
                "来源类别": info.get("来源类别") or category,
                "父词来源类别": category,
                "是否扩展": "是" if expanded_flag else "否",
                "使用规则": rule,
                "来源位置": info.get("来源位置", ""),
                "页面原文/所属路径": info.get(
                    "页面原文/所属路径", ""
                ),
                "提取理由": info.get("提取理由", ""),
                "截图编号": info.get("截图编号", "")
            }

            if record not in provenance[candidate]:
                provenance[candidate].append(record)

    for seed in seeds:
        infos = sources.get(seed.lower(), [])

        if not infos:
            infos = [{
                "来源类别": "未在来源表中找到",
                "来源位置": "",
                "页面原文/所属路径": "",
                "提取理由": "",
                "截图编号": ""
            }]

        # 1. 保留种子原词
        add(
            seed,
            seed,
            "页面目标词",
            False,
            "保留B组seeds.txt原始词",
            infos
        )

        # 2. 小写转换
        lower = seed.lower()

        if lower != seed:
            add(
                lower,
                seed,
                "目标词扩展（大小写转换）",
                True,
                f"转为小写：{seed} -> {lower}",
                infos
            )

        # 3. 原词简单单复数扩展
        p = plural(seed)

        if p and p != seed:
            add(
                p,
                seed,
                "目标词扩展（简单词形）",
                True,
                f"简单单复数规则：{seed} -> {p}",
                infos
            )

        # 4. 小写词简单单复数扩展
        lp = plural(lower)

        if lower != seed and lp and lp != lower:
            add(
                lp,
                seed,
                "目标词扩展（简单词形）",
                True,
                f"小写词形规则：{lower} -> {lp}",
                infos
            )

        # 5. 拼写纠正规则
        # 保留原词，纠正后的词作为独立候选加入
        for corrected in SPELLING_CORRECTIONS.get(lower, []):
            add(
                corrected,
                seed,
                "目标词扩展（拼写纠错）",
                True,
                f"拼写纠正规则：{seed} -> {corrected}；保留原词",
                infos
            )

        # 6. 文件后缀规则
        # 仅对种子原词及小写词追加.txt和.html
        # 不与其他扩展规则进行组合
        for form in dict.fromkeys([seed, lower]):
            for suffix in (".txt", ".html"):
                add(
                    form + suffix,
                    seed,
                    "目标词扩展（文件后缀）",
                    True,
                    f"文件后缀规则：{form} -> {form + suffix}",
                    infos
                )

        # 7. API前缀规则
        for form in dict.fromkeys([seed, lower]):
            add(
                "api/" + form,
                seed,
                "目标词扩展（API前缀）",
                True,
                f"API前缀规则：{form} -> api/{form}",
                infos
            )

    # 保持旧脚本顺序：种子及其扩展在前，基线在后。
    for item in baseline:
        add(
            item,
            item,
            "通用基线字典",
            False,
            "来自baseline_1000.txt",
            []
        )

    # 输出两个字典文件
    write_list(
        ROOT / "baseline_plus_seeds.txt",
        baseline_plus
    )

    write_list(
        ROOT / "expanded_original.txt",
        expanded
    )

    # 输出候选来源表
    fields = [
        "候选",
        "原始词",
        "来源类别",
        "父词来源类别",
        "是否扩展",
        "使用规则",
        "来源位置",
        "页面原文/所属路径",
        "提取理由",
        "截图编号"
    ]

    with (
        ROOT / "候选来源表.csv"
    ).open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        for candidate in expanded:
            for record in provenance[candidate]:
                writer.writerow(record)

    # 三阶段字典核验：项数、空行、重复数、SHA-256。
    checks = []

    for filename in (
        "baseline_1000.txt",
        "baseline_plus_seeds.txt",
        "expanded_original.txt"
    ):
        path = ROOT / filename

        values = path.read_text(
            encoding="utf-8-sig"
        ).splitlines()

        checks.append({
            "文件": filename,
            "项数": len(values),
            "空行数": sum(
                not x.strip()
                for x in values
            ),
            "重复数": len(values) - len(set(values)),
            "SHA-256": sha256(path)
        })

    with (
        ROOT / "字典核验记录.csv"
    ).open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "文件",
                "项数",
                "空行数",
                "重复数",
                "SHA-256"
            ]
        )

        writer.writeheader()
        writer.writerows(checks)

    # 生成过程示例
    (ROOT / "生成过程示例.txt").write_text(
        "真实输入词：course\n"
        "来源：B组seeds.txt；页面原文为Course（课程大纲与教学安排）。\n"
        "原词保留：course\n"
        "简单单复数扩展：courses（不以s结尾，追加s）。\n"
        "文件后缀扩展：course.txt、course.html。\n"
        "API前缀扩展：api/course。\n"
        "拼写纠正规则：若原词为subdmain，额外记录subdomain，原词保留。\n"
        "本轮种子均为小写，因此不额外产生大小写转换候选。\n"
        "候选不代表路径真实存在；本脚本只生成文件，不发送HTTP请求。\n",
        encoding="utf-8"
    )

    # 打印生成结果
    print("========== C组第二轮字典生成结果 ==========")
    print("目标词数量：", len(seeds))
    print("基线有效去重数量：", len(baseline))
    print("baseline_plus_seeds.txt：", len(baseline_plus))
    print("expanded_original.txt：", len(expanded))
    print(
        "候选来源记录数：",
        sum(len(v) for v in provenance.values())
    )

    for item in checks:
        print(
            "{}：{}项，空行{}，重复{}，SHA-256 {}".format(
                item["文件"],
                item["项数"],
                item["空行数"],
                item["重复数"],
                item["SHA-256"]
            )
        )

    print(
        "已生成：baseline_plus_seeds.txt、"
        "expanded_original.txt、候选来源表.csv、"
        "字典核验记录.csv、生成过程示例.txt"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("运行失败：", exc)
        sys.exit(1)