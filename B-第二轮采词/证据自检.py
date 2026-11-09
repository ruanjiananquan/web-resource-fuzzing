# -*- coding: utf-8 -*-
"""B 第二轮采词：证据自检
逐条回查 seeds.txt 与 词语来源表 中的引文是否真实出现在 A 提供的冻结首页里。
用法：python 证据自检.py
输出：证据自检报告.txt（同目录）
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [
    os.path.join(HERE, "..", "repo", "web-resource-fuzzing-main", "交付-A（第二轮）", "lab-extra-home.html"),
    os.path.join(HERE, "lab-extra-home.html"),
    os.path.join(HERE, "..", "交付-A（第二轮）", "lab-extra-home.html"),
]
HOME = None
for c in CANDIDATES:
    if os.path.exists(c):
        HOME = os.path.abspath(c)
        break
if HOME is None:
    print("找不到冻结首页 lab-extra-home.html，请把它放到本脚本同目录后重试")
    sys.exit(1)

html = open(HOME, encoding="utf-8").read()
lines = []
ok = 0
bad = 0


def check(cond, msg):
    global ok, bad
    if cond:
        ok += 1
        lines.append("[通过] " + msg)
    else:
        bad += 1
        lines.append("[失败] " + msg)


lines.append("=" * 60)
lines.append("B 第二轮采词 证据自检")
lines.append("冻结首页：" + HOME)
lines.append("首页行数：%d　字节数：%d" % (len(html.splitlines()), len(html.encode("utf-8"))))
lines.append("=" * 60)

# 1. 首页无链接
n_a = len(re.findall(r"<a\b", html, flags=re.I))
n_href = len(re.findall(r"href\s*=", html, flags=re.I))
check(n_a == 0, "首页 <a> 标签数量为 0（实际 %d）" % n_a)
check(n_href == 0, "首页 href 出现次数为 0（实际 %d）" % n_href)

# 2. seeds.txt 每个词都能在首页找到原文
seeds_path = os.path.join(HERE, "seeds.txt")
seeds = [s.strip() for s in open(seeds_path, encoding="utf-8").read().splitlines() if s.strip()]
check(len(seeds) > 0, "seeds.txt 非空，共 %d 词" % len(seeds))
check(len(set(seeds)) == len(seeds), "seeds.txt 无重复词")
check(all(s == s.lower() for s in seeds), "seeds.txt 全部为小写（转写规则一致）")

for w in seeds:
    m = re.search(re.escape(w), html, flags=re.I)
    if m:
        orig = m.group(0)
        line_no = html[:m.start()].count("\n") + 1
        check(True, "种子 %-10s 命中首页第 %d 行，原文写作 %s" % (w, line_no, orig))
    else:
        check(False, "种子 %-10s 在首页中找不到" % w)

# 3. 来源表逐行回查
xlsx = os.path.join(HERE, "词语来源表-第二轮.xlsx")
if os.path.exists(xlsx):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx)
    ws = wb["目标词"]
    head = [c.value for c in ws[1]]
    idx_word = head.index("词语")
    idx_src = head.index("页面原文 / 所属路径")
    idx_pos = head.index("来源位置")
    idx_shot = head.index("截图编号")
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    check(len(rows) == len(seeds), "来源表目标词行数 %d 与 seeds.txt 一致" % len(rows))
    for r in rows:
        w = r[idx_word]
        src = str(r[idx_src] or "")
        pos = str(r[idx_pos] or "")
        shot = str(r[idx_shot] or "")
        check(w in seeds, "来源表中的词语 %s 出现在 seeds.txt" % w)
        check(src in html, "来源表中 %s 的页面原文逐字存在于首页" % w)
        check("18081/lab-extra" in pos, "来源表中 %s 的定位指向 18081/lab-extra" % w)
        check(shot.startswith("图1"), "来源表中 %s 标注了截图编号 %s" % (w, shot))
    # 卡片数量
    n_card = len(re.findall(r'class="card"', html))
    check(n_card == 6, "首页卡片数量为 6（实际 %d），与 6 个种子一一对应" % n_card)
else:
    lines.append("[跳过] 未找到 词语来源表-第二轮.xlsx，跳过来源表回查")

# 4. 与第一轮交叉核对
round1 = os.path.join(HERE, "..", "B目标信息采集", "seeds.txt")
if os.path.exists(round1):
    old = set(s.strip() for s in open(round1, encoding="utf-8").read().splitlines() if s.strip())
    same = old & set(seeds)
    lines.append("[说明] 与第一轮 %d 词的重合数：%d %s" % (len(old), len(same), sorted(same) if same else ""))
    lines.append("[说明] 本轮为第二个靶场（自建受控测试集），两轮词表分开统计，不做合并")

lines.append("-" * 60)
lines.append("结果：通过 %d 项，失败 %d 项" % (ok, bad))
lines.append("判定：" + ("全部通过，种子与引文可逐条回查" if bad == 0 else "存在失败项，需修正后再交 C"))
report = "\n".join(lines)
open(os.path.join(HERE, "证据自检报告.txt"), "w", encoding="utf-8").write(report)
print(report)
sys.exit(0 if bad == 0 else 2)
