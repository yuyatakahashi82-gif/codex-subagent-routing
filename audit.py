#!/usr/bin/env python3
"""Codex の rollout ログから spawn_agent 呼び出しを抽出し、モデル明示指定率を集計する。
あわせて、親/子・モデル/推論強度ごとのトークン使用量（token_usage_record）を集計する。
使い方: python3 audit.py [YYYY/MM]   (省略時は今月)"""
import sys, json, glob, os, collections, datetime
home = os.path.expanduser("~/.codex/sessions")
ym = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().strftime("%Y/%m")
by = collections.defaultdict(collections.Counter)
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
tok = collections.defaultdict(collections.Counter)   # (役割, モデル/effort) -> usage 合計
sessions = collections.Counter()                     # (役割, モデル/effort) -> セッション数
for fn in glob.glob(f"{home}/{ym}/*/rollout-*.jsonl"):
    day = fn.split("/")[-2]
    role, me = None, None
    for line in open(fn, encoding="utf-8", errors="ignore"):
        try:
            o = json.loads(line)
        except Exception:
            continue
        t, p = o.get("type"), o.get("payload", {})
        if t == "session_meta" and role is None:
            role = "子" if p.get("thread_source") == "subagent" else "親"
        # モデル/effortはファイル内の最初のturn_contextに固定する。
        # 後続turn_contextでモデル/effortが変わっても、以降の使用量は最初の組に集計する。
        # 最初のturn_contextより前の使用量は「?」に集計し、後から再分類しない。
        elif t == "turn_context" and me is None:
            m, e = p.get("model") or "?", p.get("effort") or "?"
            me = f"{m}/{e}"
            sessions[(role or "親", me)] += 1
        elif t == "token_usage_record":
            u = p.get("usage", {})
            for k in USAGE_KEYS:
                tok[(role or "親", me or "?")][k] += u.get(k, 0)
        elif t == "response_item" and p.get("type") == "function_call" and p.get("name") == "spawn_agent":
            try:
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

# --- トークン使用量（親/子・モデル/推論強度別） ---
# 「非キャッシュ入力」= input_tokens - cached_input_tokens。上限消費の目安は非キャッシュ入力 + 出力（推論を含む）。
if tok:
    print("---")
    print("トークン使用量（token_usage_record の合計。単位: 千トークン）")
    print(f"{'役割':<3} {'モデル/推論強度':<24} {'セッション':>8} {'非キャッシュ入力':>14} {'キャッシュ入力':>12} {'出力':>8} {'うち推論':>8}")
    grand = collections.Counter()
    for (role, me), u in sorted(tok.items(), key=lambda kv: (kv[0][0], -(kv[1]["input_tokens"] - kv[1]["cached_input_tokens"] + kv[1]["output_tokens"]))):
        unc = u["input_tokens"] - u["cached_input_tokens"]
        print(f"{role:<3} {me:<24} {sessions[(role, me)]:>8} {unc/1000:>14,.0f} {u['cached_input_tokens']/1000:>12,.0f} {u['output_tokens']/1000:>8,.1f} {u['reasoning_output_tokens']/1000:>8,.1f}")
        grand["unc"] += unc; grand["out"] += u["output_tokens"]
    print(f"合計: 非キャッシュ入力 {grand['unc']/1000:,.0f}k / 出力 {grand['out']/1000:,.1f}k")
