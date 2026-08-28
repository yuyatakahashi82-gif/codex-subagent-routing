#!/usr/bin/env python3
"""Codex の rollout ログから spawn_agent 呼び出しを抽出し、モデル明示指定率を集計する。
使い方: python3 audit.py [YYYY/MM]   (省略時は今月)"""
import sys, json, glob, os, collections, datetime
home = os.path.expanduser("~/.codex/sessions")
ym = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y/%m")
by = collections.defaultdict(collections.Counter)
for fn in glob.glob(f"{home}/{ym}/*/rollout-*.jsonl"):
    day = fn.split("/")[-2]
    for line in open(fn, encoding="utf-8", errors="ignore"):
        if '"spawn_agent"' not in line:
            continue
        try:
            p = json.loads(line).get("payload", {})
            if p.get("type") != "function_call" or p.get("name") != "spawn_agent":
                continue
            a = json.loads(p.get("arguments", "{}"))
        except Exception:
            continue
        m, e = a.get("model") or "", a.get("reasoning_effort") or ""
        key = f"{m}/{e}" if (m and e) else "(親を継承)"
        by[day][key] += 1
total = collections.Counter()
for day in sorted(by):
    print(f"{ym}/{day}", dict(by[day])); total.update(by[day])
n = sum(total.values()); inh = total.get("(親を継承)", 0)
print("---")
print("合計", dict(total))
if n:
    print(f"spawn {n} 件 / 明示指定 {n-inh} 件 ({(n-inh)*100//n}%) / 親継承 {inh} 件")
    if inh == n:
        print("!! 全件が親継承です。AGENTS.md が読まれていないか、CLI 経由（model 引数なし）の可能性があります")
else:
    print("spawn_agent の呼び出しが見つかりません（期間指定を確認: 例 python3 audit.py 2026/08）")
