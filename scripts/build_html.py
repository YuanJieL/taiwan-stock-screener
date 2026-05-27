"""
AI 法人戰情室 — build_html.py
科技風 UI + AI 評分 + 多空燈號 + 回測統計
"""

import json
import os
from datetime import datetime, timezone, timedelta


def load_data():
    with open("data/latest.json", encoding="utf-8") as f:
        return json.load(f)


def fmt_date(s):
    try:
        return datetime.strptime(s, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        return s


def fmt_gain(g):
    if g is None:
        return "—"
    sign = "+" if g >= 0 else ""
    return f"{sign}{g:.1f}%"


def gain_color(g):
    if g is None:
        return "#888"
    if g >= 50:
        return "#00ff88"
    if g >= 30:
        return "#00cc66"
    if g >= 15:
        return "#66ffaa"
    if g >= 0:
        return "#aaa"
    return "#ff4466"


def ai_bar(score):
    pct = min(score, 100)
    if pct >= 70:
        color = "#00ff88"
    elif pct >= 50:
        color = "#ffcc00"
    else:
        color = "#ff4466"
    return (
        '<div style="display:flex;align-items:center;gap:6px;">'
        '<div style="flex:1;background:#1a2a1a;border-radius:3px;height:6px;overflow:hidden;">'
        f'<div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>'
        '</div>'
        f'<span style="color:{color};font-size:12px;font-weight:700;min-width:32px;">{score}</span>'
        '</div>'
    )


def build_row(s):
    bt          = s.get("backtest", {})
    passed      = bt.get("passed_15pct")
    gain_future = bt.get("gain_after_20d")
    buy_price   = bt.get("buy_price", s.get("close"))
    price_now   = bt.get("price_after_20d")
    date_future = fmt_date(bt.get("date_after_20d", "")) if bt.get("date_after_20d") else "—"
    signal_date = fmt_date(s.get("signal_date", ""))
    ai_score    = s.get("ai_score", 0)
    signal      = s.get("signal", "—")

    if passed is True:
        result_td = '<span style="color:#00ff88;font-weight:700;">✅ 通過</span>'
    elif passed is False:
        result_td = '<span style="color:#ff4466;font-weight:700;">❌ 未達</span>'
    else:
        result_td = '<span style="color:#ffcc00;font-weight:700;">⏳ 觀察</span>'

    price_now_str = f"{price_now:,.1f}" if price_now else "—"
    buy_price_str = f"{buy_price:,.1f}" if buy_price else "—"
    gc_20d = gain_color(s["gain_20d"])
    gc_fut = gain_color(gain_future)

    cells = [
        f'<td><span class="code-chip">{s["code"]}</span></td>',
        f'<td style="font-weight:500;color:#e0f0ff;">{s["name"]}</td>',
        f'<td class="dim">{signal_date}</td>',
        f'<td style="color:#7dd3fc;">{buy_price_str}</td>',
        f'<td style="color:#e0f0ff;">{price_now_str}</td>',
        f'<td style="color:{gc_20d};font-weight:700;">{fmt_gain(s["gain_20d"])}</td>',
        f'<td><span class="ratio-chip">{s["inst_ratio"]:.1f}%</span></td>',
        f'<td style="color:{gc_fut};font-weight:700;">{fmt_gain(gain_future)}</td>',
        f'<td class="dim">{date_future}</td>',
        f'<td>{result_td}</td>',
        f'<td>{ai_bar(ai_score)}</td>',
        f'<td style="font-size:12px;">{signal}</td>',
    ]
    return "<tr>" + "".join(cells) + "</tr>"


CSS = """
*, *::before, *::after { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang TC', sans-serif;
  background: #050d0f;
  color: #c0d8e0;
  line-height: 1.6;
  font-size: 14px;
}
a { color: #00ccff; text-decoration: none; }
a:hover { color: #00ffff; }
.topbar {
  background: linear-gradient(90deg, #001a22 0%, #002a3a 50%, #001a22 100%);
  border-bottom: 1px solid #00ccff33;
  padding: 1rem 2rem;
  display: flex; align-items: center; justify-content: space-between;
}
.topbar-left h1 {
  font-size: 1.4rem; font-weight: 700;
  color: #00ffff;
  text-shadow: 0 0 20px #00ccff88;
  letter-spacing: 2px;
}
.topbar-left p { font-size: .75rem; color: #4a8fa8; margin-top: 2px; }
.topbar-right { font-size: .75rem; color: #4a8fa8; text-align: right; }
.topbar-right strong { color: #00ccff; }
.wrap { max-width: 1400px; margin: 0 auto; padding: 1.5rem 1rem; }
.condition {
  background: #001a22; border: 1px solid #00ccff22;
  border-radius: 8px; padding: .6rem 1rem;
  font-size: .78rem; color: #4a8fa8; margin-bottom: 1.2rem;
}
.condition strong { color: #00ccff; }
.stats {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 10px; margin-bottom: 1.4rem;
}
.stat {
  background: #001a22;
  border: 1px solid #00ccff22;
  border-radius: 10px; padding: .75rem .5rem; text-align: center;
  transition: border-color .2s;
}
.stat:hover { border-color: #00ccff66; }
.stat .num { font-size: 1.4rem; font-weight: 700; }
.stat .lbl { font-size: .65rem; color: #4a8fa8; margin-top: 3px; letter-spacing: .5px; }
.card {
  background: #001a22;
  border: 1px solid #00ccff22;
  border-radius: 12px; overflow: hidden; margin-bottom: 1.4rem;
}
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 1100px; }
thead tr {
  background: linear-gradient(90deg, #002233, #003344, #002233);
  border-bottom: 1px solid #00ccff33;
}
th {
  padding: 10px 12px; text-align: left;
  font-weight: 600; color: #00ccff;
  font-size: 12px; letter-spacing: .5px;
  white-space: nowrap;
}
td {
  padding: 9px 12px;
  border-bottom: 1px solid #001a2266;
  vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: #002233aa; }
.dim { color: #4a8fa8; font-size: 12px; }
.code-chip {
  background: #002233; border: 1px solid #00ccff44;
  color: #00ccff; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 700; letter-spacing: 1px;
}
.ratio-chip {
  background: #001a33; border: 1px solid #0088ff44;
  color: #66aaff; padding: 2px 8px; border-radius: 4px;
  font-size: 12px; font-weight: 600;
}
@keyframes scan {
  0%   { transform: translateY(-100%); opacity: 0; }
  50%  { opacity: .3; }
  100% { transform: translateY(100vh); opacity: 0; }
}
.scanline {
  position: fixed; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, #00ffff88, transparent);
  animation: scan 4s linear infinite; pointer-events: none; z-index: 9999;
}
.empty { text-align: center; padding: 3rem; color: #4a8fa8; }
.footer {
  font-size: .72rem; color: #2a5a6a; line-height: 1.9;
  margin-top: 1rem; border-top: 1px solid #00ccff11; padding-top: 1rem;
}
@media (max-width: 768px) {
  .stats { grid-template-columns: repeat(4, 1fr); }
  .topbar { flex-direction: column; gap: .5rem; }
}
@media (max-width: 480px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
}
"""


def build_html(data):
    date_raw = data.get("date", "")
    hist_raw = data.get("hist_date", "")
    gen_at   = data.get("generated_at", "")
    stocks   = data.get("stocks", [])
    stats    = data.get("backtest_stats", {})
    status   = data.get("status", "")

    date_fmt = fmt_date(date_raw)
    hist_fmt = fmt_date(hist_raw)

    try:
        utc_dt  = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        tpe_dt  = utc_dt.astimezone(timezone(timedelta(hours=8)))
        gen_fmt = tpe_dt.strftime("%Y/%m/%d %H:%M")
    except Exception:
        gen_fmt = gen_at

    passed_count = sum(1 for s in stocks if s.get("backtest", {}).get("passed_15pct") is True)
    watch_count  = sum(1 for s in stocks if s.get("backtest", {}).get("passed_15pct") is None)
    failed_count = sum(1 for s in stocks if s.get("backtest", {}).get("passed_15pct") is False)
    total        = len(stocks)

    win_rate   = (str(stats["win_rate"]) + "%") if stats.get("win_rate") is not None else "—"
    avg_return = fmt_gain(stats.get("avg_return"))
    max_dd     = fmt_gain(stats.get("max_drawdown"))
    max_gain   = fmt_gain(stats.get("max_gain"))

    if status == "no_data":
        body = '<div class="empty">今日無交易資料</div>'
    elif not stocks:
        body = '<div class="empty">今日無符合條件個股</div>'
    else:
        rows  = "\n".join(build_row(s) for s in stocks)
        thead = (
            "<thead><tr>"
            "<th>代號</th><th>名稱</th><th>訊號日</th>"
            "<th>買入價</th><th>現價</th><th>近20日漲幅</th>"
            "<th>法人占比</th><th>回測漲幅</th><th>回測日</th>"
            "<th>結果</th><th>AI評分</th><th>燈號</th>"
            "</tr></thead>"
        )
        body = (
            '<div class="table-wrap">'
            f"<table>{thead}<tbody>{rows}</tbody></table>"
            "</div>"
        )

    stats_html = (
        '<div class="stats">'
        f'<div class="stat"><div class="num" style="color:#00ff88;">{passed_count}</div><div class="lbl">✅ 回測通過</div></div>'
        f'<div class="stat"><div class="num" style="color:#ffcc00;">{watch_count}</div><div class="lbl">⏳ 觀察中</div></div>'
        f'<div class="stat"><div class="num" style="color:#ff4466;">{failed_count}</div><div class="lbl">❌ 未達標</div></div>'
        f'<div class="stat"><div class="num" style="color:#00ccff;">{total}</div><div class="lbl">📊 總計</div></div>'
        f'<div class="stat"><div class="num" style="color:#00ff88;">{win_rate}</div><div class="lbl">🎯 回測勝率</div></div>'
        f'<div class="stat"><div class="num" style="color:#66ffaa;">{avg_return}</div><div class="lbl">📈 平均報酬</div></div>'
        f'<div class="stat"><div class="num" style="color:#ff4466;">{max_dd}</div><div class="lbl">📉 最大回撤</div></div>'
        f'<div class="stat"><div class="num" style="color:#00ff88;">{max_gain}</div><div class="lbl">🚀 最大漲幅</div></div>'
        "</div>"
    )

    html = (
        "<!DOCTYPE html>\n"
        '<html lang="zh-Hant">\n'
        "<head>\n"
        '<meta charset="UTF-8"/>\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1"/>\n'
        f"<title>AI 法人戰情室 | {date_fmt}</title>\n"
        f"<style>{CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="scanline"></div>\n'
        '<div class="topbar">\n'
        '  <div class="topbar-left">\n'
        "    <h1>⚡ AI 法人戰情室</h1>\n"
        "    <p>Institutional AI Trading War Room · TWSE 上市股票</p>\n"
        "  </div>\n"
        '  <div class="topbar-right">\n'
        f"    <div>📅 資料日期：<strong>{date_fmt}</strong></div>\n"
        f"    <div>📅 回測基準：<strong>{hist_fmt}</strong></div>\n"
        f"    <div>🕐 更新：<strong>{gen_fmt}</strong></div>\n"
        "  </div>\n"
        "</div>\n"
        '<div class="wrap">\n'
        '  <div class="condition">\n'
        "    <strong>篩選：</strong>三大法人淨買超 / 總成交量 &gt; 10%　且　近20交易日漲幅 &gt; 30%\n"
        "    　｜　<strong>回測：</strong>當天收盤買入，20交易日後漲幅 ≥ 15%\n"
        "    　｜　<strong>AI評分：</strong>法人強度 × 40% + 趨勢動能 × 40% + 回測績效 × 20%\n"
        "  </div>\n"
        f"  {stats_html}\n"
        '  <div class="card">\n'
        f"    {body}\n"
        "  </div>\n"
        '  <div class="footer">\n'
        "    ⚠ 本頁面資訊僅供參考，不構成任何投資建議。AI評分為量化模型輸出，不保證未來績效。<br/>\n"
        "    資料來源：臺灣證券交易所（TWSE）公開資訊。\n"
        '    <a href="data/latest.json" target="_blank">📄 JSON</a> &nbsp;|&nbsp;\n'
        '    <a href="https://www.twse.com.tw" target="_blank">TWSE</a> &nbsp;|&nbsp;\n'
        '    <a href="https://github.com/YuanJieL/taiwan-stock-screener" target="_blank">GitHub</a>\n'
        "  </div>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )
    return html


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)

    if not os.path.exists("data/latest.json"):
        placeholder = {
            "date": datetime.today().strftime("%Y%m%d"),
            "hist_date": "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_data",
            "backtest_stats": {},
            "stocks": []
        }
        os.makedirs("data", exist_ok=True)
        with open("data/latest.json", "w", encoding="utf-8") as f:
            json.dump(placeholder, f, ensure_ascii=False, indent=2)

    data = load_data()
    html = build_html(data)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    passed = sum(1 for s in data.get("stocks", []) if s.get("backtest", {}).get("passed_15pct") is True)
    total  = len(data.get("stocks", []))
    print(f"✅ AI 法人戰情室 HTML 已產生（回測通過：{passed} / 共 {total} 檔）")