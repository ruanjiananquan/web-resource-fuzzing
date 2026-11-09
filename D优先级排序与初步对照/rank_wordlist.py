#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path


def level(record):
    """为单条来源记录分层"""
    expanded = record['是否扩展']
    if expanded == '是': return 3
    if expanded != '否': raise ValueError('不明确的扩展标记：' + str(record))
    category = record['来源类别']
    if category == '通用基线字典': return 4
    original = record['原始词']
    if record['候选'] != original:
        raise ValueError('非扩展记录的候选与原词不同：' + str(record))
    if '路径片段' in category or '脚本文件名' in category: return 1
    if '页面文字' in category: return 2
    raise ValueError('未知原词来源类别：' + original)


def main():
    """读取候选和来源，生成完整排序；在指定时输出截断版本。"""
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description='四级规则排序与可复现随机排序对照')

    parser.add_argument('--candidates', type=Path, default=root/'candidates.txt')
    parser.add_argument('--provenance', type=Path, default=root/'候选来源表.csv')
    parser.add_argument('--seeds', type=int, nargs='+', default=[2026, 2027, 2028], help='随机种子，默认2026 2027 2028')
    parser.add_argument('--limit', type=int, help='可选，另存各组前N项，完整字典仍保留')
    parser.add_argument('--output-dir', type=Path, default=root)
    args = parser.parse_args()
    candidates = args.candidates.read_text(encoding='utf-8-sig').splitlines()
    if not candidates or any(not x or x!=x.strip() for x in candidates):
        raise ValueError('候选为空，或有空行、首尾空格')
    if args.limit is not None and not 1 <= args.limit <= len(candidates):
        raise ValueError('截取项数必须在1与候选总数之间')
    if len(set(args.seeds))!=len(args.seeds):
        raise ValueError('随机种子不能重复')
    if len(set(candidates))!=len(candidates):
        raise ValueError('候选有完全重复项')
    for item in candidates:
        parts=item.rstrip('/').split('/')
        if item.startswith('/') or chr(92) in item or any(t in item for t in ['://','?','#']):
            raise ValueError('不允许的候选：'+item)
        if any(p in ('','.','..') for p in parts):
            raise ValueError('不允许的路径段：'+item)
    records=defaultdict(list)
    with args.provenance.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        required={'候选','原始词','来源类别','是否扩展'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('来源表缺少字段：'+ '、'.join(sorted(required-set(reader.fieldnames or []))))
        for row in reader: records[row['候选']].append(row)
    if set(records)!=set(candidates):
        raise ValueError('来源表与候选集合不一致')
    # 多来源候选取最高优先级；同层按长度、字符序排列，保留大小写。
    levels={x:min(level(r) for r in records[x]) for x in candidates}
    ranked=sorted(candidates,key=lambda x:(levels[x],len(x),x))
    # 每个随机组从相同的字符序列表开始，避免组间相互影响。
    outputs={'ranked':ranked}
    for seed in args.seeds:
        shuffled=sorted(candidates)
        random.Random(seed).shuffle(shuffled)
        if set(ranked)!=set(shuffled): raise ValueError('完整集合不一致')
        outputs[f'random_{seed}']=shuffled
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name,words in outputs.items():
        (args.output_dir/f'{name}_full.txt').write_text('\n'.join(words)+'\n',encoding='utf-8')
        if args.limit is not None:
            (args.output_dir/f'{name}_{args.limit}.txt').write_text('\n'.join(words[:args.limit])+'\n',encoding='utf-8')
    print('完整集合一致；候选共',len(candidates),'项。')
    print('四层数量：',*[sum(v==i for v in levels.values()) for i in (1,2,3,4)])
    print('随机种子：',*args.seeds)
    print('完整字典数量：',len(outputs),'；截取项数：',args.limit if args.limit is not None else '未截取')


if __name__=='__main__':
    main()
