#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import random
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def source_words(path):
    """读取 B 的目标词工作表"""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', ns):
                strings.append(''.join(x.text or '' for x in si.findall('.//s:t', ns)))
        book = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(x for x in book.findall('s:sheets/s:sheet', ns) if x.get('name') == '目标词')
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(x.get('Target') for x in rels if x.get('Id') == sheet.get(rns))
        target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        rows = []
        for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row', ns):
            cells = {}
            for c in row.findall('s:c', ns):
                v = c.find('s:v', ns)
                text = v.text if v is not None and v.text else ''
                if c.get('t') == 's': text = strings[int(text)]
                if c.get('t') == 'inlineStr': text = ''.join(x.text or '' for x in c.findall('.//s:t', ns))
                col = ''.join(ch for ch in c.get('r') if ch.isalpha())
                cells[col] = text
            rows.append(cells)
        headers = rows[0]
        wc = next(k for k, v in headers.items() if v == '词语')
        cc = next(k for k, v in headers.items() if v == '来源类别')
        result = defaultdict(list)
        for row in rows[1:]:
            if row.get(wc): result[row[wc]].append(row.get(cc, ''))
        return result


def level(record, sources):
    """为单条来源记录分层"""
    expanded = record['是否扩展']
    if expanded == '是': return 3
    if expanded != '否': raise ValueError('不明确的扩展标记：' + str(record))
    category = record['来源类别']
    if category == '通用基线字典': return 4
    original = record['原始词']
    if record['候选'] != original:
        raise ValueError('非扩展记录的候选与原词不同：' + str(record))
    if original not in sources: raise ValueError('B 来源表未找到原词：' + original)
    categories = '；'.join(sources[original])
    if '路径片段' in categories or '脚本文件名' in categories: return 1
    if '页面文字' in categories: return 2
    raise ValueError('未知原词来源类别：' + original)


def main():
    """核对候选来源，固定规则和随机种子，输出四份字典。"""
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--candidates', type=Path, default=root/'candidates.txt')
    parser.add_argument('--provenance', type=Path, default=root/'候选来源表.csv')
    parser.add_argument('--sources', type=Path, default=root/'词语来源表.xlsx')
    parser.add_argument('--output-dir', type=Path, default=root)
    args = parser.parse_args()
    candidates = args.candidates.read_text(encoding='utf-8-sig').splitlines()
    if len(candidates)<1000 or any(not x or x!=x.strip() for x in candidates):
        raise ValueError('候选少于1000项，或有空行、首尾空格')
    if len(set(candidates))!=len(candidates):
        raise ValueError('候选有完全重复项')
    for item in candidates:
        parts=item.rstrip('/').split('/')
        if item.startswith('/') or chr(92) in item or any(t in item for t in ['://','?','#']):
            raise ValueError('不允许的候选：'+item)
        if any(p in ('','.','..') or p.lower() in ('rate','limited') for p in parts):
            raise ValueError('不允许的路径段：'+item)
    sources=source_words(args.sources)
    records=defaultdict(list)
    with args.provenance.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f): records[row['候选']].append(row)
    if set(records)!=set(candidates):
        raise ValueError('来源表与候选集合不一致')
    # 多来源候选取最高优先级；同层按长度、字符序排列，保留大小写。
    levels={x:min(level(r,sources) for r in records[x]) for x in candidates}
    ranked=sorted(candidates,key=lambda x:(levels[x],len(x),x))
    # 固定初始顺序与随机种子2026，保证同样输入能重现随机对照。
    shuffled=sorted(candidates)
    random.Random(2026).shuffle(shuffled)
    if set(ranked)!=set(shuffled): raise ValueError('两份完整集合不一致')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,words in [('ranked_full.txt',ranked),('random_full.txt',shuffled),
                       ('ranked_1000.txt',ranked[:1000]),('random_1000.txt',shuffled[:1000])]:
        (args.output_dir/name).write_text('\n'.join(words)+'\n',encoding='utf-8')
    print('完整集合一致；候选共',len(candidates),'项。')
    print('四层数量：',*[sum(v==i for v in levels.values()) for i in (1,2,3,4)])
    print('已生成两份完整排序字典、两份前1000项字典。')


if __name__=='__main__':
    main()
