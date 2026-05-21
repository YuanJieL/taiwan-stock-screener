"""
台股三大法人選股篩選器
篩選條件：
  1. 法人淨買量 / 當日總成交量 > 10%
  2. 近20個交易日漲幅 > 30%
回測：符合條件當天收盤買入，20個交易日後是否再漲15%以上
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

def get_prev_trading_day() -> str:
    today = datetime.today()
    offset = 1
    if today.weekday() == 0:
        offset = 3
    elif today.weekday() == 6:
        offset = 2
    return (today - timedelta(days=offset)).strftime("%Y%m%d")


# ──────────────────────────────────────────────
# 1. 三大法人買賣超
# ──────────────────────────────────────────────
def fetch_institutional(date_str: str) -> pd.DataFrame:
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

    df = pd.DataFrame(data["data"], columns=data["fields"])
    df = df.rename(columns={
        "證券代號": "code",
        "證券名稱": "name",
        "三大法人買賣超股數": "inst_net",
    })

    def clean(s):
        try:
            return int(str(s).replace(",", "").replace("+", ""))
        except Exception:
            return 0

    df["inst_net"] = df["inst_net"].apply(clean)
    return df[["code", "name", "inst_net"]].copy()


# ──────────────────────────────────────────────
# 2. 當日成交量與收盤價
# ──────────────────────────────────────────────
def fetch_daily_volume(date_str: str) -> pd.DataFrame:
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL"
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

    df = pd.DataFrame(data["data"], columns=data["fields"])

    col_map = {}
    for col in df.columns:
        if "代號" in col or "代碼" in col:
            col_map[col] = "code"
        elif "成交股數" in col or "成交量" in col:
            col_map[col] = "volume"
        elif "收盤" in col and "close" not in col_map.values():
            col_map[col] = "close"

    df = df.rename(columns=col_map)
    keep = [c for c in ["code", "volume", "close"] if c in df.columns]
    df = df[keep].copy()

    def clean(s):
        try:
            return float(str(s).replace(",", ""))
        except Exception:
            return 0.0

    if "volume" in df.columns:
        df["volume"] = df["volume"].apply(clean)
    if "close" in df.columns:
        df["close"] = df["close"].apply(clean)

    return df


# ──────────────────────────────────────────────
# 3. 個股歷史收盤價（近兩個月）
# ──────────────────────────────────────────────
def fetch_price_history(stock_code: str, date_str: str) -> list:
    prices = []
    for offset in [1, 0]:
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
# 4. 回測：買入後20交易日是否再漲15%
# ──────────────────────────────────────────────
def fetch_future_price(stock_code: str, buy_date_str: str) -> dict:
    """
    從買入日起，取得之後約3個月的收盤價，
    回傳 20個交易日後的價格與漲幅
    """
    future_prices = []
    buy_dt = datetime.strptime(buy_date_str, "%Y%m%d")

    for offset in [0, 1, 2]:
        ym = (buy_dt + timedelta(days=30 * offset)).strftime("%Y%m01")
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
                        # row[0] = 民國日期，row[6] = 收盤價
                        roc_date = row[0].strip()
                        parts = roc_date.split("/")
                        ad_year = int(parts[0]) + 1911
                        row_dt = datetime(ad_year, int(parts[1]), int(parts[2]))
                        close = float(row[6].replace(",", ""))
                        future_prices.append((row_dt, close))
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(0.3)

    # 找買入日之後的價格
    future_prices = sorted(future_prices, key=lambda x: x[0])
    after_buy = [(dt, p) for dt, p in future_prices if dt > buy_dt]

    if len(after_buy) < 20:
        return {"status": "insufficient", "days": len(after_buy)}

    price_20d = after_buy[19][1]   # 第20個交易日收盤價
    date_20d = after_buy[19][0].strftime("%Y/%m/%d")

    return {
        "status": "ok",
        "price_20d": price_20d,
        "date_20d": date_20d,
    }


# ──────────────────────────────────────────────
# 5. 主篩選 + 回測邏輯
# ──────────────────────────────────────────────
def run_screener(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = get_prev_trading_day()

    print(f"\n=== 執行日期：{date_str} ===")

    inst_df = fetch_institutional(date_str)
    if inst_df.empty:
        return {"date": date_str, "status": "no_data", "stocks": []}

    vol_df = fetch_daily_volume(date_str)

    if not vol_df.empty:
        merged = inst_df.merge(vol_df, on="code", how="left")
    else:
        merged = inst_df.copy()
        merged["volume"] = 0.0
        merged["close"] = 0.0

    merged["inst_ratio"] = merged.apply(
        lambda r: (r["inst_net"] / r["volume"] * 100) if r["volume"] > 0 else 0,
        axis=1
    )

    candidates = merged[merged["inst_ratio"] > 10].copy()
    print(f"法人買超比率 >10% 候選：{len(candidates)} 檔")

    if candidates.empty:
        return {"date": date_str, "status": "ok", "stocks": []}

    results = []
    for _, row in candidates.iterrows():
        code = row["code"].strip()
        name = row.get("name", "")
        time.sleep(0.5)

        # 近20交易日漲幅
        prices = fetch_price_history(code, date_str)
        if len(prices) < 21:
            continue

        price_20d_ago = prices[-21]
        price_buy = prices[-1]   # 當天收盤 = 買入價

        if price_20d_ago <= 0:
            continue

        gain_20d = (price_buy - price_20d_ago) / price_20d_ago * 100

        if gain_20d < 30:
            continue

        print(f"  📌 {code} {name}  近20日 +{gain_20d:.1f}%  法人占比 {row['inst_ratio']:.1f}%  → 進行回測...")

        # 回測：買入後20交易日
        backtest = fetch_future_price(code, date_str)

        if backtest["status"] == "insufficient":
            # 資料不足（可能還沒過20交易日，代表是近期訊號）
            gain_future = None
            passed = None
            price_future = None
            date_future = None
            note = f"尚未滿20交易日（現有{backtest['days']}日）"
        else:
            price_future = backtest["price_20d"]
            date_future = backtest["date_20d"]
            gain_future = (price_future - price_buy) / price_buy * 100
            passed = gain_future >= 15
            note = f"買入後20日 {'✅ 上漲' if passed else '❌ 未達'} {gain_future:.1f}%"

        print(f"     回測結果：{note}")

        results.append({
            "code": code,
            "name": name,
            "close": round(price_buy, 2),
            "gain_20d": round(gain_20d, 2),
            "inst_net_shares": int(row["inst_net"]),
            "inst_ratio": round(row["inst_ratio"], 2),
            "volume_shares": int(row.get("volume", 0)),
            "backtest": {
                "buy_price": round(price_buy, 2),
                "price_after_20d": round(price_future, 2) if price_future else None,
                "date_after_20d": date_future,
                "gain_after_20d": round(gain_future, 2) if gain_future is not None else None,
                "passed_15pct": passed,
                "note": note,
            }
        })

    # 排序：回測通過的優先，其次依近20日漲幅
    def sort_key(x):
        p = x["backtest"]["passed_15pct"]
        if p is True:
            return (0, -x["gain_20d"])
        if p is None:
            return (1, -x["gain_20d"])
        return (2, -x["gain_20d"])

    results.sort(key=sort_key)

    output = {
        "date": date_str,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "ok",
        "stocks": results,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    passed = [s for s in results if s["backtest"]["passed_15pct"] is True]
    print(f"\n✅ 回測通過（漲幅≥15%）：{len(passed)} 檔")
    print(f"📊 篩選結果共：{len(results)} 檔 → data/latest.json")
    return output


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_screener(date_arg)
