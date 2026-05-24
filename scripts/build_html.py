"""
根據 data/latest.json 產生 docs/index.html（GitHub Pages 用）
上市 + 上櫃合併版
"""

import json
import os
from datetime import datetime, timezone, timedelta


def load_data():
    with open("data/latest.json", encoding="utf-8") as f:
        return json.load(f)


def status_badge(passed):
    if passed is True:
        return '<span style="background:#EAF3DE;color:#27500A;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;">✅ 通過 +15%</span>'
    if passed is False:
        return '<span style="background:#FCEBEB;color:#791F1F;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;">❌ 未達標</span>'
    return '<span style="background:#FAEEDA;color:#633806;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;">⏳ 觀察中</span>'


def market_badge(market):
    if market == "上市":
        return '<span style="background:#E6F1FB;color:#0C447C;padding:2px 6px;border-radius:4px;font-size:11px;">上市</span>'
    return '<span style="background:#F0EBF8;color:#4A2580;padding:2px 6px;border-radius:4px;font-size:11px;">上櫃</span>'


def gain_color(g):
    if g is None:
        return "#888780"
    if g >= 50:
        return "#27500A"
    if g >= 30:
        return "#3B6D11"
    if g >= 15:
        return "#639922"
    if g >= 0:
        return "#888780"
    return "#A32D2D"


def build_row(s):
    bt = s.get("backtest", {})
    passed = bt.get("passed_15pct")
    gain_future = bt.get("gain_after_20d")
    price_future = bt.get("price_after_20d")
    date_future = bt.get("date_after_20d", "—")
    buy_price = bt.get("buy_price", s.get("close", "—"))

    gain_future_str = (
        f"+{gain_future:.1f}%" if gain_future and gain_future >= 0
        else (f"{gain_future:.1f}%" if gain_future is not None else "—")
    )

    signal_date = s.get("signal_date", "")
    try:
        sd = datetime.strptime(signal_date, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        sd = signal_date

    return f"""
    <tr>
      <td style="padding:10px 12px;font-weight:500;">{s['code']}</td>
      <td style="padding:10px 12px;">{s['name']}</td>
      <td style="padding:10px 12px;">{market_badge(s.get('market',''))}</td>
      <td style="padding:10px 12px;font-size:12px;color:#666;">{sd}</td>
      <td style="padding:10px 12px;font-weight:500;">{buy_price} 元</td>
      <td style="padding:10px 12px;font-weight:500;">{s['close']:,.1f} 元</td>
      <td style="padding:10px 12px;color:{gain_color(s['gain_20d'])};font-weight:500;">+{s['gain_20d']:.1f}%</td>
      <td style="padding:10px 12px;">
        <span style="background:#E6F1FB;color:#185FA5;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;">{s['inst_ratio']:.1f}%</span>
      </td>
      <td style="padding:10px 12px;color:{gain_color(gain_future)};font-weight:500;">{gain_future_str}</td>
      <td style="padding:10px 12px;">{status_badge(passed)}</td>
    </tr>"""


def build_html(data):
    date_raw = data.get("date", "")
    hist_date_raw = data.get("hist_date", "")
    gen_at = data.get("generated_at", "")
    stocks = data.get("stocks", [])
    status = data.get("status", "")

    try:
        date_fmt = datetime.strptime(date_raw, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        date_fmt = date_raw

    try:
        hist_fmt = datetime.strptime(hist_date_raw, "%Y%m%d").strftime("%Y/%m/%d")
    except Exception:
        hist_fmt = hist_date_raw

    try:
        utc_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        tpe_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
        gen_fmt = tpe_dt.strftime("%Y/%m/%d %H:%M（台北時間）")
    except Exception:
        gen_fmt = gen_at

    passed_count = len([s for s in stocks if s.get("backtest", {}).get("passed_15pct") is True])
    watching_count = len([s for s in stocks if s.get("backtest", {}).get("passed_15pct") is None])
    failed_count = len([s for s in stocks if s.get("backtest", {}).get("passed_15pct") is False])
    twse_count = len([s for s in stocks if s.get("market") == "上市"])
    tpex_count = len([s for s in stocks if s.get("market") == "上櫃"])

    if status == "no_data":
        body_content = '<div style="text-align:center;padding:3rem;color:#888;"><p>今日無交易資料</p></div>'
    elif not stocks:
        body_content = '<div style="text-align:center;padding:3rem;color:#888;"><p>今日無符合條件個股</p></div>'
    else:
        rows_html = "".join(build_row(s) for s in stocks)
        body_content = f"""
        <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;font-size:14px;min-width:900px;">
          <thead>
            <tr style="background:#f5f5f3;border-bottom:1px solid #ddd;">
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">代號</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">名稱</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">市場</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">訊號日期</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">買入價</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">現價</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">近20日漲幅</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">法人買超占比</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">回測20日漲幅</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;white-space:nowrap;">回測結果</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>台股三大法人選股（上市+上櫃）| {date_fmt}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7f7f5;color:#1a1a18;line-height:1.6}}
    a{{color:#185FA5;text-decoration:none}}
    .wrap{{max-width:1200px;margin:0 auto;padding:2rem 1rem}}
    .header h1{{font-size:1.5rem;font-weight:500;margin-bottom:.3rem}}
    .header p{{font-size:.85rem;color:#666;margin-bottom:1.2rem}}
    .condition{{background:#fff;border:0.5px solid #e0e0de;border-radius:8px;padding:.8rem 1rem;font-size:.8rem;color:#666;margin-bottom:1rem}}
    .condition strong{{color:#1a1a18}}
    .meta{{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1rem}}
    .chip{{background:#fff;border:0.5px solid #ddd;border-radius:6px;padding:.35rem .8rem;font-size:.8rem;color:#555}}
    .chip strong{{color:#1a1a18}}
    .stats{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:1.5rem}}
    .stat{{background:#fff;border:0.5px solid #e0e0de;border-radius:8px;padding:.8rem;text-align:center}}
    .stat .num{{font-size:1.5rem;font-weight:500}}
    .stat .label{{font-size:.7rem;color:#888;margin-top:2px}}
    .card{{background:#fff;border:0.5px solid #e0e0de;border-radius:12px;overflow:hidden;margin-bottom:1.5rem}}
    tr:hover{{background:#fafaf8}}
    .footer{{font-size:.75rem;color:#999;margin-top:1.5rem;line-height:1.8}}
    @media(max-width:600px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🔍 台股三大法人選股篩選器（上市 + 上櫃）</h1>
    <p>每個交易日自動執行，同時涵蓋 TWSE 上市與 TPEx 上櫃股票</p>
  </div>

  <div class="condition">
    <strong>篩選條件：</strong>三大法人淨買超占比 &gt; 10%　且　近20交易日漲幅 &gt; 30%
    　｜　
    <strong>回測：</strong>當天收盤買入，20個交易日後漲幅是否 ≥ 15%
  </div>

  <div class="meta">
    <span class="chip">📅 今日資料：<strong>{date_fmt}</strong></span>
    <span class="chip">📅 回測基準日：<strong>{hist_fmt}</strong></span>
    <span class="chip">🕐 更新時間：<strong>{gen_fmt}</strong></span>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="num" style="color:#27500A;">{passed_count}</div>
      <div class="label">✅ 回測通過</div>
    </div>
    <div class="stat">
      <div class="num" style="color:#BA7517;">{watching_count}</div>
      <div class="label">⏳ 觀察中</div>
    </div>
    <div class="stat">
      <div class="num" style="color:#A32D2D;">{failed_count}</div>
      <div class="label">❌ 未達標</div>
    </div>
    <div class="stat">
      <div class="num" style="color:#0C447C;">{twse_count}</div>
      <div class="label">📈 上市個股</div>
    </div>
    <div class="stat">
      <div class="num" style="color:#4A2580;">{tpex_count}</div>
      <div class="label">📊 上櫃個股</div>
    </div>
  </div>

  <div class="card">
    {body_content}
  </div>

  <div class="footer">
    ⚠ 本頁面資訊僅供參考，不構成任何投資建議。股市投資有風險，請自行評估。<br/>
    資料來源：臺灣證券交易所（TWSE）、櫃買中心（TPEx）公開資訊。<br/>
    <a href="data/latest.json" target="_blank">📄 下載原始 JSON</a>
    &nbsp;|&nbsp;
    <a href="https://www.twse.com.tw" target="_blank">TWSE</a>
    &nbsp;|&nbsp;
    <a href="https://www.tpex.org.tw" target="_blank">TPEx</a>
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
            "generated_at": datetime.utcnow().isoformat() + "Z",
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

    passed = len([s for s in data.get("stocks", []) if s.get("backtest", {}).get("passed_15pct") is True])
    print(f"✅ docs/index.html 已產生（回測通過：{passed} 檔）")
