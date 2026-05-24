"""
根據 data/latest.json 產生 docs/index.html（GitHub Pages 用）
上市版 + ETF 標示 + 回測結果完整顯示
"""

import json
import os
from datetime import datetime, timezone, timedelta


def load_data():
    with open("data/latest.json", encoding="utf-8") as f:
        return json.load(f)


def fmt_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        return date_str


def status_badge(passed):
    if passed is True:
        return '<span class="badge badge-pass">✅ 回測通過</span>'
    if passed is False:
        return '<span class="badge badge-fail">❌ 未達標</span>'
    return '<span class="badge badge-watch">⏳ 觀察中</span>'


def type_badge(code, name):
    code = str(code).strip()
    etf_kw = ["ETF","正二","反一","反向","槓桿","基金","高股息","ESG","永續","債券","期貨","商品"]
    is_etf = len(code) > 4 or any(k in str(name) for k in etf_kw)
    if is_etf:
        return '<span class="badge badge-etf">📦 ETF</span>'
    return '<span class="badge badge-stock">📈 個股</span>'


def gain_color(g):
    if g is None: return "#888"
    if g >= 50:   return "#1a5c06"
    if g >= 30:   return "#3B6D11"
    if g >= 15:   return "#639922"
    if g >= 0:    return "#888"
    return "#A32D2D"


def fmt_gain(g):
    if g is None: return "—"
    sign = "+" if g >= 0 else ""
    return f"{sign}{g:.1f}%"


def build_row(s):
    bt = s.get("backtest", {})
    passed      = bt.get("passed_15pct")
    gain_future = bt.get("gain_after_20d")
    price_now   = bt.get("price_after_20d")
    buy_price   = bt.get("buy_price", s.get("close", "—"))
    date_future = fmt_date(bt.get("date_after_20d", "")) if bt.get("date_after_20d") else "—"
    signal_date = fmt_date(s.get("signal_date", ""))
    gc_20d = gain_color(s["gain_20d"])
    gc_fut = gain_color(gain_future)
    price_now_str = f"{price_now:,.1f}" if price_now else "—"

    return f"""<tr>
      <td><strong>{s['code']}</strong></td>
      <td>{s['name']}</td>
      <td>{type_badge(s['code'], s['name'])}</td>
      <td class="dim">{signal_date}</td>
      <td><strong>{buy_price:,.1f}</strong></td>
      <td><strong>{price_now_str}</strong></td>
      <td style="color:{gc_20d};font-weight:600;">{fmt_gain(s['gain_20d'])}</td>
      <td><span class="ratio-chip">{s['inst_ratio']:.1f}%</span></td>
      <td style="color:{gc_fut};font-weight:600;">{fmt_gain(gain_future)}</td>
      <td class="dim">{date_future}</td>
      <td>{status_badge(passed)}</td>
    </tr>"""


def build_html(data):
    date_raw      = data.get("date", "")
    hist_date_raw = data.get("hist_date", "")
    gen_at        = data.get("generated_at", "")
    stocks        = data.get("stocks", [])
    status        = data.get("status", "")

    date_fmt = fmt_date(date_raw)
    hist_fmt = fmt_date(hist_date_raw)

    try:
        utc_dt  = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        tpe_dt  = utc_dt.astimezone(timezone(timedelta(hours=8)))
        gen_fmt = tpe_dt.strftime("%Y/%m/%d %H:%M（台北時間）")
    except Exception:
        gen_fmt = gen_at

    passed_count = sum(1 for s in stocks if s.get("backtest",{}).get("passed_15pct") is True)
    watch_count  = sum(1 for s in stocks if s.get("backtest",{}).get("passed_15pct") is None)
    failed_count = sum(1 for s in stocks if s.get("backtest",{}).get("passed_15pct") is False)
    stock_count  = sum(1 for s in stocks if len(str(s.get("code","")).strip()) <= 4)
    etf_count    = sum(1 for s in stocks if len(str(s.get("code","")).strip()) > 4)
    win_rate     = f"{passed_count/(passed_count+failed_count)*100:.0f}%" if (passed_count+failed_count) > 0 else "—"

    if status == "no_data":
        body = '<div class="empty">今日無交易資料（假日或資料尚未更新）</div>'
    elif not stocks:
        body = '<div class="empty">今日無符合條件個股</div>'
    else:
        rows = "".join(build_row(s) for s in stocks)
        body = f"""<div class="table-wrap">
        <table>
          <thead><tr>
            <th>代號</th><th>名稱</th><th>類型</th><th>訊號日</th>
            <th>買入價</th><th>現價</th><th>近20日漲幅</th>
            <th>法人占比</th><th>回測漲幅</th><th>回測日</th><th>結果</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table></div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>台股法人選股 | {date_fmt}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang TC', sans-serif;
      background: #f4f4f2; color: #1a1a18; line-height: 1.6; font-size: 14px;
    }}
    a {{ color: #185FA5; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 1300px; margin: 0 auto; padding: 1.5rem 1rem; }}
    .header {{ margin-bottom: 1.2rem; }}
    .header h1 {{ font-size: 1.4rem; font-weight: 600; margin-bottom: .2rem; }}
    .header p  {{ font-size: .82rem; color: #666; }}
    .condition {{
      background: #fff; border: 0.5px solid #e0e0de; border-radius: 8px;
      padding: .65rem 1rem; font-size: .8rem; color: #555; margin-bottom: 1rem;
    }}
    .condition strong {{ color: #1a1a18; }}
    .meta {{ display: flex; gap: .6rem; flex-wrap: wrap; margin-bottom: 1rem; }}
    .chip {{
      background: #fff; border: 0.5px solid #ddd; border-radius: 6px;
      padding: .3rem .75rem; font-size: .78rem; color: #555;
    }}
    .chip strong {{ color: #1a1a18; }}
    .stats {{
      display: grid; grid-template-columns: repeat(6, 1fr);
      gap: 10px; margin-bottom: 1.4rem;
    }}
    .stat {{
      background: #fff; border: 0.5px solid #e0e0de; border-radius: 10px;
      padding: .75rem .5rem; text-align: center;
    }}
    .stat .num {{ font-size: 1.5rem; font-weight: 600; }}
    .stat .lbl {{ font-size: .7rem; color: #888; margin-top: 2px; }}
    .card {{
      background: #fff; border: 0.5px solid #e0e0de;
      border-radius: 12px; overflow: hidden; margin-bottom: 1.4rem;
    }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; min-width: 960px; }}
    thead tr {{ background: #f5f5f3; border-bottom: 1px solid #e0e0de; }}
    th {{
      padding: 10px 12px; text-align: left;
      font-weight: 500; color: #555; white-space: nowrap; font-size: 13px;
    }}
    td {{ padding: 9px 12px; border-bottom: .5px solid #f0f0ee; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafaf8; }}
    .dim {{ color: #888; font-size: 12px; }}
    .badge {{
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 11px; font-weight: 500; white-space: nowrap;
    }}
    .badge-pass  {{ background: #EAF3DE; color: #27500A; }}
    .badge-fail  {{ background: #FCEBEB; color: #791F1F; }}
    .badge-watch {{ background: #FAEEDA; color: #633806; }}
    .badge-stock {{ background: #E6F1FB; color: #0C447C; }}
    .badge-etf   {{ background: #F0EBF8; color: #4A2580; }}
    .ratio-chip {{
      background: #E6F1FB; color: #185FA5;
      padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500;
    }}
    .empty {{ text-align: center; padding: 3rem; color: #888; font-size: 1rem; }}
    .footer {{ font-size: .73rem; color: #aaa; line-height: 1.9; margin-top: 1rem; }}
    @media (max-width: 600px) {{
      .stats {{ grid-template-columns: repeat(3, 1fr); }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🔍 台股三大法人選股篩選器</h1>
    <p>每個交易日自動執行 — TWSE 上市股票（含 ETF）</p>
  </div>
  <div class="condition">
    <strong>篩選：</strong>三大法人淨買超 / 總成交量 &gt; 10%　且　近20交易日漲幅 &gt; 30%
    　｜　<strong>回測：</strong>當天收盤買入，20交易日後漲幅是否 ≥ 15%
  </div>
  <div class="meta">
    <span class="chip">📅 今日資料：<strong>{date_fmt}</strong></span>
    <span class="chip">📅 回測基準：<strong>{hist_fmt}（20交易日前）</strong></span>
    <span class="chip">🕐 更新：<strong>{gen_fmt}</strong></span>
  </div>
  <div class="stats">
    <div class="stat"><div class="num" style="color:#27500A;">{passed_count}</div><div class="lbl">✅ 回測通過</div></div>
    <div class="stat"><div class="num" style="color:#BA7517;">{watch_count}</div><div class="lbl">⏳ 觀察中</div></div>
    <div class="stat"><div class="num" style="color:#A32D2D;">{failed_count}</div><div class="lbl">❌ 未達標</div></div>
    <div class="stat"><div class="num" style="color:#185FA5;">{stock_count}</div><div class="lbl">📈 個股</div></div>
    <div class="stat"><div class="num" style="color:#4A2580;">{etf_count}</div><div class="lbl">📦 ETF</div></div>
    <div class="stat"><div class="num" style="color:#185FA5;">{win_rate}</div><div class="lbl">🎯 回測勝率</div></div>
  </div>
  <div class="card">{body}</div>
  <div class="footer">
    ⚠ 本頁面資訊僅供參考，不構成任何投資建議。股市投資有風險，請自行評估。<br/>
    資料來源：臺灣證券交易所（TWSE）公開資訊。<br/>
    <a href="data/latest.json" target="_blank">📄 原始 JSON</a> &nbsp;|&nbsp;
    <a href="https://www.twse.com.tw" target="_blank">TWSE 官網</a> &nbsp;|&nbsp;
    <a href="https://github.com/YuanJieL/taiwan-stock-screener" target="_blank">GitHub</a>
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)

    if not os.path.exists("data/latest.json"):
        placeholder = {
            "date": datetime.today().strftime("%Y%m%d"),
            "hist_date": "",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_data",
            "stocks": []
        }
        os.makedirs("data", exist_ok=True)
        with open("data/latest.json", "w", encoding="utf-8") as f:
            json.dump(placeholder, f, ensure_ascii=False, indent=2)

    data = load_data()
    html = build_html(data)

    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    passed = sum(1 for s in data.get("stocks",[]) if s.get("backtest",{}).get("passed_15pct") is True)
    total  = len(data.get("stocks", []))
    print(f"✅ docs/index.html 已產生（回測通過：{passed} / 共 {total} 檔）")
