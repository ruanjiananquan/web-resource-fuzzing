
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
C组 Web 资源模糊测试候选字典生成程序

输入：
    seeds.txt
    baseline_1000.txt
    词语来源表.xlsx
    公开路径清单.xlsx

输出：
    candidates.txt
    候选来源表.csv
    生成过程示例.txt

默认开启 api/ 前缀扩展。
如需关闭，使用 --no-api。
"""

from pathlib import Path
from collections import defaultdict
import argparse
import csv
import re
import sys

try:
    import openpyxl
except ImportError:
    print("缺少依赖 openpyxl，请执行：py -3 -m pip install openpyxl")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent

SEEDS_FILE = ROOT / "seeds.txt"
BASELINE_FILE = ROOT / "baseline_1000.txt"
SOURCE_FILE = ROOT / "词语来源表.xlsx"
PUBLIC_FILE = ROOT / "公开路径清单.xlsx"

# 保留原拼写，同时增加单独的纠错候选。
SPELLING_CORRECTIONS = {
    "subdmain": ["subdomain"]
}


def read_lines(path):
    """读取文本，删除空行和首尾空格。"""
    if not path.exists():
        raise FileNotFoundError("找不到输入文件：" + path.name)

    return [
        line.strip()
        for line in path.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        if line.strip()
    ]


def get_cell(row, index, name):
    """安全读取 Excel 单元格。"""
    if name not in index:
        return ""

    value = row[index[name]]

    if value is None:
        return ""

    return str(value).strip()


def load_excel_sheet(path, sheet_name):
    """读取指定 Excel 工作表。"""
    if not path.exists():
        raise FileNotFoundError("找不到输入文件：" + path.name)

    book = openpyxl.load_workbook(path, data_only=True)

    if sheet_name not in book.sheetnames:
        raise ValueError(
            "{} 中找不到工作表：{}".format(path.name, sheet_name)
        )

    sheet = book[sheet_name]

    headers = [cell.value for cell in sheet[1]]

    index = {
        name: headers.index(name)
        for name in headers
        if name is not None
    }

    return sheet, index


def load_source_info(path):
    """读取目标词来源表，保留同一词的多条来源。"""
    sheet, index = load_excel_sheet(path, "目标词")

    result = defaultdict(list)

    for row in sheet.iter_rows(min_row=2, values_only=True):
        word = get_cell(row, index, "词语")

        if not word:
            continue

        # 兼容表头中斜杠前后有无空格的情况。
        page_text = (
            get_cell(row, index, "页面原文/所属路径")
            or get_cell(row, index, "页面原文 / 所属路径")
        )

        info = {
            "来源类别": get_cell(row, index, "来源类别"),
            "来源位置": get_cell(row, index, "来源位置"),
            "页面原文/所属路径": page_text,
            "提取理由": get_cell(row, index, "提取理由"),
            "截图编号": get_cell(row, index, "截图编号"),
        }

        result[word.lower()].append(info)

    return result


def load_public_paths(path):
    """读取公开路径清单，仅用于公开状态标记。"""
    if not path.exists():
        print("提示：未找到公开路径清单，不进行公开路径标记。")
        return []

    sheet, index = load_excel_sheet(path, "公开路径")

    result = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        raw_path = get_cell(row, index, "路径")
        include = get_cell(row, index, "是否进入候选")

        if include != "是" or not raw_path.startswith("/"):
            continue

        result.append({
            "path": raw_path.lstrip("/"),
            "absolute": raw_path,
            "type": get_cell(row, index, "类型"),
            "location": get_cell(row, index, "页面中的位置"),
            "note": get_cell(row, index, "备注"),
        })

    return result


def allowed_candidate(value):
    """
    候选合法性检查。

    允许：
        .git/logs/
        abc/
        api/install

    排除：
        /absolute/path
        ../abc
        abc/../def
        abc//def
        http://example.com
        含问号或井号的内容
        含反斜杠的内容
        rate、limited 路径段
    """

    value = value.strip()

    if not value:
        return False

    if "://" in value or "?" in value or "#" in value:
        return False

    if value.startswith("/") or value.startswith("\\"):
        return False

    if "\\" in value:
        return False

    parts = value.split("/")

    # 允许一个末尾斜杠。
    if value.endswith("/"):
        parts = parts[:-1]

    if any(part in ("", ".", "..") for part in parts):
        return False

    # 排除限速练习相关路径段。
    if any(
        part.lower() in ("rate", "limited")
        for part in parts
    ):
        return False

    return True


def plural_variant(word):
    """
    严格按照老师规定的简单词形规则：

    纯英文词：
    1. 不以 s 结尾：追加 s。
    2. 以 s 结尾且长度大于 3：删除末尾 s。

    不是完整英语语法处理，只是启发式候选生成。
    """

    if not re.fullmatch(r"[A-Za-z]+", word):
        return None

    if len(word) > 3 and word.lower().endswith("s"):
        return word[:-1]

    return word + "s"


def main():

    parser = argparse.ArgumentParser(
        description="C组 Web 资源模糊测试候选字典生成程序"
    )

    # 默认开启 API 扩展。
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="关闭 api/ 前缀扩展"
    )

    args = parser.parse_args()

    include_api = not args.no_api

    # 读取输入。
    seeds_raw = read_lines(SEEDS_FILE)
    baseline_raw = read_lines(BASELINE_FILE)

    source_info = load_source_info(SOURCE_FILE)
    public_paths = load_public_paths(PUBLIC_FILE)

    # 删除目标词完全重复项，保留第一次出现的原始拼写。
    seeds = list(dict.fromkeys(seeds_raw))

    # 建立公开路径索引。
    public_by_path = {}

    for item in public_paths:
        key = item["path"].rstrip("/").lower()
        public_by_path[key] = item

    # 清洗基线字典。
    baseline_valid = [
        item for item in baseline_raw
        if allowed_candidate(item)
    ]

    baseline_invalid_count = (
        len(baseline_raw) - len(baseline_valid)
    )

    baseline_unique = list(dict.fromkeys(baseline_valid))

    baseline_duplicate_count = (
        len(baseline_valid) - len(baseline_unique)
    )

    # 候选和来源记录。
    candidates = []
    provenance = defaultdict(list)

    def add(
        candidate,
        original,
        category,
        expanded,
        rule,
        info_list=None
    ):
        candidate = candidate.strip()

        if not allowed_candidate(candidate):
            return

        # 候选列表按首次出现顺序去重。
        if candidate not in provenance:
            candidates.append(candidate)

        # 公开路径只作标记，不独立加入候选。
        normalized = candidate.rstrip("/").lower()
        pub = public_by_path.get(normalized)

        if not info_list:
            info_list = [{}]

        for info in info_list:

            record = {
                "候选": candidate,
                "原始词": original,
                "来源类别": (
                    info.get("来源类别") or category
                ),
                "父词来源类别": category,
                "是否扩展": "是" if expanded else "否",
                "使用规则": rule,
                "来源位置": info.get("来源位置", ""),
                "页面原文/所属路径": info.get(
                    "页面原文/所属路径", ""
                ),
                "提取理由": info.get("提取理由", ""),
                "截图编号": info.get("截图编号", ""),
                "公开状态": (
                    "已公开" if pub else "未标记为公开"
                ),
                "对应公开路径": (
                    pub["absolute"] if pub else ""
                ),
                "公开路径备注": (
                    pub["note"] if pub else ""
                ),
            }

            # 防止同一候选的完全相同来源记录重复。
            if record not in provenance[candidate]:
                provenance[candidate].append(record)

    # --------------------------------------------------
    # 第一步：处理 B 组目标词。
    # --------------------------------------------------

    for seed in seeds:

        info_list = source_info.get(seed.lower(), [])

        if not info_list:
            info_list = [{
                "来源类别": "未在词语来源表中找到",
                "来源位置": "",
                "页面原文/所属路径": "",
                "提取理由": "",
                "截图编号": "",
            }]

        # 1. 保留原始词。
        add(
            seed,
            seed,
            "目标词",
            False,
            "保留 B 组提供的原始拼写",
            info_list
        )

        # 2. 生成小写形式。
        lower = seed.lower()

        if lower != seed:
            add(
                lower,
                seed,
                "目标词扩展（大小写转换）",
                True,
                "转为小写：{} -> {}".format(seed, lower),
                info_list
            )

        # 3. 按老师规定生成原始拼写的单复数候选。
        plural = plural_variant(seed)

        if plural and plural != seed:
            add(
                plural,
                seed,
                "目标词扩展（简单词形）",
                True,
                "简单词形规则：{} -> {}".format(seed, plural),
                info_list
            )

        # 4. 对小写形式也应用相同规则。
        if lower != seed:
            lower_plural = plural_variant(lower)

            if lower_plural and lower_plural != lower:
                add(
                    lower_plural,
                    seed,
                    "目标词扩展（简单词形）",
                    True,
                    "小写词形规则：{} -> {}".format(
                        lower, lower_plural
                    ),
                    info_list
                )

        # 5. 拼写纠错：保留原词，纠错词单独记录。
        for corrected in SPELLING_CORRECTIONS.get(
            lower, []
        ):
            add(
                corrected,
                seed,
                "目标词扩展（拼写纠错）",
                True,
                "单独记录拼写纠错：{} -> {}；原词保留".format(
                    seed, corrected
                ),
                info_list
            )

        # 6. API 前缀扩展，默认开启。
        # 对原始词和小写形式分别生成。
        if include_api:

            api_forms = [seed]

            if lower != seed:
                api_forms.append(lower)

            for form in dict.fromkeys(api_forms):
                add(
                    "api/" + form,
                    seed,
                    "目标词扩展（API前缀）",
                    True,
                    "API 前缀规则：{} -> api/{}".format(
                        form, form
                    ),
                    info_list
                )

    # --------------------------------------------------
    # 第二步：合并基线字典。
    # --------------------------------------------------

    for item in baseline_unique:
        add(
            item,
            item,
            "通用基线字典",
            False,
            "来自 baseline_1000.txt"
        )

    # --------------------------------------------------
    # 第三步：输出完整候选字典。
    # --------------------------------------------------

    candidates_file = ROOT / "candidates.txt"

    candidates_file.write_text(
        "\n".join(candidates) + "\n",
        encoding="utf-8"
    )

    # --------------------------------------------------
    # 第四步：输出候选来源表。
    # --------------------------------------------------

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
        "截图编号",
        "公开状态",
        "对应公开路径",
        "公开路径备注",
    ]

    csv_file = ROOT / "候选来源表.csv"

    with csv_file.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fields
        )

        writer.writeheader()

        for candidate in candidates:
            for record in provenance[candidate]:
                writer.writerow(record)

    # --------------------------------------------------
    # 第五步：输出生成过程示例。
    # --------------------------------------------------

    example_word = (
        "install"
        if "install" in seeds
        else (seeds[0] if seeds else "")
    )

    if example_word:

        example_forms = [example_word]

        lower = example_word.lower()

        if lower != example_word:
            example_forms.append(lower)

        plural = plural_variant(example_word)

        if plural:
            example_forms.append(plural)

        if lower != example_word:
            lower_plural = plural_variant(lower)

            if lower_plural:
                example_forms.append(lower_plural)

        corrected = SPELLING_CORRECTIONS.get(lower, [])
        example_forms.extend(corrected)

        if include_api:
            example_forms.append("api/" + example_word)

            if lower != example_word:
                example_forms.append("api/" + lower)

        public_match = public_by_path.get(
            example_word.rstrip("/").lower()
        )

        example_lines = [
            "真实输入词：" + example_word,
            "来源：seeds.txt；页面证据见词语来源表.xlsx。",
            "生成规则：保留原词、生成小写形式和简单词形扩展。",
            "本例候选：" + "、".join(
                dict.fromkeys(example_forms)
            ),
            "API 前缀扩展：" + (
                "已开启，生成 api/原词及 api/小写词形式。"
                if include_api
                else "已关闭。"
            ),
            "公开路径核对：" + (
                "该词在公开路径清单中标记为已公开。"
                if public_match
                else "该词未在公开路径清单中匹配到。"
            ),
            "注意：候选不代表路径真实存在；已公开路径不能计为新发现。",
            "边界：排除 /cd/rate 及 rate、limited 路径段。",
            "subdmain 原拼写保留；subdomain 作为单独的拼写纠错扩展。",
            "单复数使用老师规定的简单启发式规则，不代表完整英语语法。",
        ]

        example_file = ROOT / "生成过程示例.txt"

        example_file.write_text(
            "\n".join(example_lines) + "\n",
            encoding="utf-8"
        )

    # --------------------------------------------------
    # 第六步：输出统计信息。
    # --------------------------------------------------

    print()
    print("========== C组字典生成结果 ==========")

    print("目标词原始数量：{}".format(len(seeds_raw)))
    print("目标词去重后数量：{}".format(len(seeds)))

    print("基线原始非空行数：{}".format(len(baseline_raw)))
    print("基线去重后有效数量：{}".format(len(baseline_unique)))
    print("基线重复数量：{}".format(baseline_duplicate_count))
    print("基线无效数量：{}".format(baseline_invalid_count))

    print("公开路径标记数量：{}".format(len(public_paths)))

    print(
        "API 前缀扩展：{}".format(
            "开启（默认）" if include_api else "关闭"
        )
    )

    print("最终去重候选数量：{}".format(len(candidates)))

    print("======================================")
    print("已生成：candidates.txt")
    print("已生成：候选来源表.csv")
    print("已生成：生成过程示例.txt")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("程序运行失败：{}".format(error))
        sys.exit(1)
