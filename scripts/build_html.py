"""
根據 data/latest.json 產生 docs/index.html（GitHub Pages 用）
"""

import json
import os
from datetime import datetime, timezone, timedelta

def load_data():
    with open("data/latest.json", encoding="utf-8") as f:
        return json.load(f)


def gain_color(g: float) -> str:
    if g >= 100:
        return "#27500A"
    if g >= 60:
        return "#3B6D11"
    if g >= 30:
        return "#639922"
    return "#888780"


def ratio_badge(r: float) -> str:
    color = "#185FA5" if r >= 20 else "#378ADD"
    return (
        f'<span style="background:#E6F1FB;color:{color};'
        f'padding:2px 8px;border-radius:4px;font-size:12px;font-weight:500;">'
        f'{r:.1f}%</span>'
    )


def build_row(s: dict) -> str:
    gc = gain_color(s["gain_20d"])
    net_k = s["inst_net_shares"] // 1000
    return f"""
    <tr>
      <td style="font-weight:500;padding:10px 12px;">{s['code']}</td>
      <td style="padding:10px 12px;">{s['name']}</td>
      <td style="padding:10px 12px;font-weight:500;font-size:15px;">{s['close']:,.1f}</td>
      <td style="padding:10px 12px;color:{gc};font-weight:500;">+{s['gain_20d']:.1f}%</td>
      <td style="padding:10px 12px;">{ratio_badge(s['inst_ratio'])}</td>
      <td style="padding:10px 12px;color:#185FA5;">{net_k:+,} 張</td>
    </tr>"""


def build_html(data: dict) -> str:
    date_raw = data.get("date", "")
    gen_at = data.get("generated_at", "")
    stocks = data.get("stocks", [])
    status = data.get("status", "")

    # 格式化日期
    try:
        d = datetime.strptime(date_raw, "%Y%m%d")
        date_fmt = d.strftime("%Y/%m/%d")
    except Exception:
        date_fmt = date_raw

    # 台北時間
    try:
        utc_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        tpe_dt = utc_dt.astimezone(timezone(timedelta(hours=8)))
        gen_fmt = tpe_dt.strftime("%Y/%m/%d %H:%M (台北時間)")
    except Exception:
        gen_fmt = gen_at

    if status == "no_data":
        body_content = """
        <div style="text-align:center;padding:3rem;color:#888;">
          <p style="font-size:1.2rem;">今日無交易資料（假日或資料尚未更新）</p>
        </div>"""
    elif not stocks:
        body_content = """
        <div style="text-align:center;padding:3rem;color:#888;">
          <p style="font-size:1.2rem;">今日無符合條件個股</p>
          <p style="font-size:0.9rem;">條件：法人淨買超占比 &gt; 10% 且 近20交易日漲幅 &gt; 30%</p>
        </div>"""
    else:
        rows_html = "".join(build_row(s) for s in stocks)
        body_content = f"""
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead>
            <tr style="background:#f5f5f3;border-bottom:1px solid #ddd;">
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">代號</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">名稱</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">收盤價 (元)</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">近20日漲幅</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">法人買超占比</th>
              <th style="padding:10px 12px;text-align:left;font-weight:500;color:#555;">三大法人淨買</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>"""

    count = len(stocks)
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>台股三大法人選股 | {date_fmt}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:#f7f7f5;color:#1a1a18;line-height:1.6}}
    a{{color:#185FA5;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    .wrap{{max-width:900px;margin:0 auto;padding:2rem 1rem}}
    .header{{margin-bottom:1.5rem}}
    .header h1{{font-size:1.5rem;font-weight:500;margin-bottom:.3rem}}
    .header p{{font-size:.85rem;color:#666}}
    .meta{{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.5rem}}
    .chip{{background:#fff;border:0.5px solid #ddd;border-radius:6px;
           padding:.35rem .8rem;font-size:.8rem;color:#555}}
    .chip strong{{color:#1a1a18}}
    .card{{background:#fff;border:0.5px solid #e0e0de;border-radius:12px;
           overflow:hidden;margin-bottom:1.5rem}}
    tr:hover{{background:#fafaf8}}
    .condition{{background:#fff;border:0.5px solid #e0e0de;border-radius:8px;
                padding:.8rem 1rem;font-size:.8rem;color:#666;margin-bottom:1rem}}
    .condition strong{{color:#1a1a18}}
    .footer{{font-size:.75rem;color:#999;margin-top:1.5rem;line-height:1.8}}
    @media(max-width:600px){{
      table thead{{display:none}}
      table,tbody,tr,td{{display:block}}
      tr{{margin-bottom:.8rem;border:0.5px solid #e0e0de;border-radius:8px;padding:.5rem .8rem}}
      td{{padding:4px 0 !important}}
      td::before{{content:attr(data-label);font-size:11px;color:#999;display:block}}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🔍 台股三大法人選股篩選器</h1>
    <p>自動每個交易日收盤後更新</p>
  </div>

  <div class="condition">
    篩選條件：
    <strong>三大法人淨買量 / 當日總成交量 &gt; 10%</strong>
    且
    <strong>近20個交易日收盤漲幅 &gt; 30%</strong>
    　|　資料來源：台灣證券交易所 TWSE 公開 API
  </div>

  <div class="meta">
    <span class="chip">📅 資料日期：<strong>{date_fmt}</strong></span>
    <span class="chip">🕐 更新時間：<strong>{gen_fmt}</strong></span>
    <span class="chip">✅ 符合條件：<strong>{count} 檔</strong></span>
  </div>

  <div class="card">
    {body_content}
  </div>

  <div class="footer">
    ⚠ 本頁面資訊僅供參考，不構成任何投資建議。股市投資有風險，請自行評估並承擔相關風險。<br/>
    資料來源：臺灣證券交易所（TWSE）公開資訊。程式自動抓取，數值如有誤差以交易所公告為準。<br/>
    <a href="data/latest.json" target="_blank">📄 下載原始 JSON</a>
    &nbsp;|&nbsp;
    <a href="https://www.twse.com.tw" target="_blank">TWSE 官網</a>
    &nbsp;|&nbsp;
    <a href="https://github.com" target="_blank">GitHub</a>
  </div>
</div>
</body>
</html>"""


if __name__ == "__main__":
    os.makedirs("docs", exist_ok=True)

    if not os.path.exists("data/latest.json"):
        # 產生空白佔位 JSON
        placeholder = {
            "date": datetime.today().strftime("%Y%m%d"),
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

    print(f"✅ docs/index.html 已產生（{len(data.get('stocks', []))} 檔個股）")
