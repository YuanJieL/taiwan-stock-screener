"""
台股三大法人選股篩選器
篩選條件：
  1. 法人淨買量 / 當日總成交量 > 10%
  2. 近20個交易日漲幅 > 30%
資料來源：TWSE 公開資料 API
"""

import requests
import json
import time
import os
from datetime import datetime, timedelta
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# ──────────────────────────────────────────────
# 1. 取得三大法人買賣超（上市，今日）
# ──────────────────────────────────────────────
def fetch_institutional_today(date_str: str) -> pd.DataFrame:
    """
    TWSE T86 — 三大法人買賣超日報
    date_str: 'YYYYMMDD'
    """
    url = (
        "https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?response=json&date={date_str}&selectType=ALL"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[institutional] 取得失敗: {e}")
        return pd.DataFrame()

    if data.get("stat") != "OK":
        print(f"[institutional] stat={data.get('stat')}, date={date_str}")
        return pd.DataFrame()

    fields = data["fields"]
    rows = data["data"]
    df = pd.DataFrame(rows, columns=fields)

    # 標準化欄位
    df = df.rename(columns={
        "證券代號": "code",
        "證券名稱": "name",
        "外陸資買進股數": "foreign_buy",
        "外陸資賣出股數": "foreign_sell",
        "投信買進股數": "trust_buy",
        "投信賣出股數": "trust_sell",
        "自營商買進股數": "dealer_buy",
        "自營商賣出股數": "dealer_sell",
        "三大法人買賣超股數": "inst_net",
    })
    keep = ["code", "name", "inst_net"]
    df = df[[c for c in keep if c in df.columns]].copy()

    def clean_num(s):
        try:
            return int(str(s).replace(",", "").replace("+", ""))
        except Exception:
            return 0

    df["inst_net"] = df["inst_net"].apply(clean_num)
    return df


# ──────────────────────────────────────────────
# 2. 取得個股當日成交量（上市）
# ──────────────────────────────────────────────
def fetch_daily_volume(date_str: str) -> pd.DataFrame:
    """
    TWSE MI_INDEX3 — 每日收盤行情
    """
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX3"
        f"?response=json&date={date_str}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[volume] 取得失敗: {e}")
        return pd.DataFrame()

    if data.get("stat") != "OK":
        print(f"[volume] stat={data.get('stat')}")
        return pd.DataFrame()

    # TWSE 可能回傳多個 tables，找包含「成交股數」的那個
    for key in ["data9", "data8", "data"]:
        if key in data:
            rows = data[key]
            fields = data.get("fields9") or data.get("fields8") or data.get("fields", [])
            break
    else:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=fields)

    col_map = {}
    for col in df.columns:
        if "代號" in col or "代碼" in col:
            col_map[col] = "code"
        elif "成交股數" in col or "成交量" in col:
            col_map[col] = "volume"
        elif "收盤" in col and "price" not in col_map.values():
            col_map[col] = "close"

    df = df.rename(columns=col_map)
    keep = [c for c in ["code", "volume", "close"] if c in df.columns]
    df = df[keep].copy()

    def clean_num(s):
        try:
            return float(str(s).replace(",", ""))
        except Exception:
            return 0.0

    if "volume" in df.columns:
        df["volume"] = df["volume"].apply(clean_num)
    if "close" in df.columns:
        df["close"] = df["close"].apply(clean_num)

    return df


# ──────────────────────────────────────────────
# 3. 取得近20交易日收盤價（用於計算漲幅）
# ──────────────────────────────────────────────
def fetch_price_history(stock_code: str, date_str: str) -> list:
    """
    TWSE STOCK_DAY — 個股月成交資訊
    回傳近兩個月的收盤價 list（舊→新）
    """
    prices = []
    for offset in [1, 0]:          # 取前一個月 + 當月
        ym = (
            datetime.strptime(date_str, "%Y%m%d")
            - timedelta(days=30 * offset)
        ).strftime("%Y%m01")
        url = (
            "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
            f"?response=json&date={ym}&stockNo={stock_code}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            data = r.json()
            if data.get("stat") == "OK":
                for row in data.get("data", []):
                    try:
                        prices.append(float(row[6].replace(",", "")))
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(0.3)
    return prices


# ──────────────────────────────────────────────
# 4. 主篩選邏輯
# ──────────────────────────────────────────────
def run_screener(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = datetime.today().strftime("%Y%m%d")

    print(f"\n=== 執行日期：{date_str} ===")

    # (A) 三大法人
    inst_df = fetch_institutional_today(date_str)
    if inst_df.empty:
        return {"date": date_str, "status": "no_data", "stocks": []}

    # (B) 日成交量 + 收盤價
    vol_df = fetch_daily_volume(date_str)

    if not vol_df.empty:
        merged = inst_df.merge(vol_df, on="code", how="left")
    else:
        merged = inst_df.copy()
        merged["volume"] = 0.0
        merged["close"] = 0.0

    # (C) 計算法人買超占比 (inst_net 單位：股 → 換算張=千股)
    #     volume 欄位為「股」，inst_net 也是「股」，直接相除即可
    merged["inst_ratio"] = merged.apply(
        lambda r: (r["inst_net"] / r["volume"] * 100) if r["volume"] > 0 else 0,
        axis=1
    )

    # 初步篩選：法人淨買超比率 > 10%
    candidates = merged[merged["inst_ratio"] > 10].copy()
    print(f"法人買超比率 >10% 候選：{len(candidates)} 檔")

    if candidates.empty:
        return {"date": date_str, "status": "ok", "stocks": []}

    # (D) 逐一取得近20交易日漲幅
    results = []
    for _, row in candidates.iterrows():
        code = row["code"].strip()
        name = row.get("name", "")
        time.sleep(0.5)   # 避免 rate limit

        prices = fetch_price_history(code, date_str)
        if len(prices) < 21:
            print(f"  {code} 歷史資料不足（{len(prices)}筆），跳過")
            continue

        price_20d_ago = prices[-21]
        price_now = prices[-1]

        if price_20d_ago <= 0:
            continue

        gain_20d = (price_now - price_20d_ago) / price_20d_ago * 100

        if gain_20d >= 30:
            results.append({
                "code": code,
                "name": name,
                "close": round(price_now, 2),
                "gain_20d": round(gain_20d, 2),
                "inst_net_shares": int(row["inst_net"]),
                "inst_ratio": round(row["inst_ratio"], 2),
                "volume_shares": int(row.get("volume", 0)),
            })
            print(f"  ✅ {code} {name}  近20日 +{gain_20d:.1f}%  法人占比 {row['inst_ratio']:.1f}%")

    output = {
        "date": date_str,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "ok",
        "stocks": sorted(results, key=lambda x: x["gain_20d"], reverse=True),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n篩選結果：{len(results)} 檔符合條件 → data/latest.json")
    return output


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_screener(date_arg)
