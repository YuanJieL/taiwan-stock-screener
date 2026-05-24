"""
台股三大法人選股篩選器（上市版 v3）
篩選條件：
  1. 法人淨買量 / 當日總成交量 > 10%
  2. 近20個交易日漲幅 > 30%
回測：20交易日前訊號，遇假日自動往後找最近交易日
資料來源：TWSE 公開資料 API
"""

import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta
import pandas as pd

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

MAX_CANDIDATES = 50


def get_prev_trading_day(base_date=None, offset=1) -> str:
    dt = base_date or datetime.today()
    days, skipped = 0, 0
    while skipped < offset:
        days += 1
        candidate = dt - timedelta(days=days)
        if candidate.weekday() < 5:
            skipped += 1
    return candidate.strftime("%Y%m%d")


def find_valid_trading_day(date_str: str, max_forward_days: int = 7) -> str:
    """從 date_str 往後找，直到 TWSE 有資料的交易日"""
    dt = datetime.strptime(date_str, "%Y%m%d")
    for i in range(max_forward_days + 1):
        candidate = dt + timedelta(days=i)
        if candidate.weekday() >= 5:
            continue
        cand_str = candidate.strftime("%Y%m%d")
        df = twse_institutional(cand_str)
        time.sleep(0.5)
        if not df.empty:
            if i > 0:
                print(f"  歷史日期 {date_str} 無資料，改用 {cand_str}")
            return cand_str
    print(f"  找不到有效交易日（{date_str} 往後 {max_forward_days} 天皆無資料）")
    return date_str


def clean_int(s) -> int:
    try:
        return int(str(s).replace(",", "").replace("+", "").replace(" ", ""))
    except Exception:
        return 0


def clean_float(s) -> float:
    try:
        v = float(str(s).replace(",", "").replace("+", "").replace(" ", ""))
        return v if v > 0 else 0.0
    except Exception:
        return 0.0


def twse_institutional(date_str: str) -> pd.DataFrame:
    url = (
        "https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?response=json&date={date_str}&selectType=ALL"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            print(f"[TWSE inst] stat={data.get('stat')}, date={date_str}")
            return pd.DataFrame()
        df = pd.DataFrame(data["data"], columns=data["fields"])
        df = df.rename(columns={
            "證券代號": "code",
            "證券名稱": "name",
            "三大法人買賣超股數": "inst_net",
        })
        df["inst_net"] = df["inst_net"].apply(clean_int)
        return df[["code", "name", "inst_net"]].copy()
    except Exception as e:
        print(f"[TWSE inst] 失敗: {e}")
        return pd.DataFrame()


def twse_volume(date_str: str) -> pd.DataFrame:
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL"
        f"?response=json&date={date_str}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            print(f"[TWSE vol] stat={data.get('stat')}")
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
        df = df[[c for c in ["code", "volume", "close"] if c in df.columns]].copy()
        for c in ["volume", "close"]:
            if c in df.columns:
                df[c] = df[c].apply(clean_float)
        return df
    except Exception as e:
        print(f"[TWSE vol] 失敗: {e}")
        return pd.DataFrame()


def twse_price_history(stock_code: str, date_str: str) -> list:
    prices = []
    dt = datetime.strptime(date_str, "%Y%m%d")
    for offset in [1, 0]:
        ym = (dt - timedelta(days=30 * offset)).strftime("%Y%m01")
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
        time.sleep(0.2)
    return prices


def build_price_cache(date_str: str, codes: list) -> dict:
    """對候選股逐一抓近兩個月收盤價 → {code: [close, ...]}"""
    cache = {}
    total = len(codes)
    for i, code in enumerate(codes, 1):
        prices = twse_price_history(code, date_str)
        if prices:
            cache[code] = prices
        if i % 10 == 0:
            print(f"  歷史價格進度：{i}/{total}")
    return cache


def build_current_price_cache(date_str: str) -> dict:
    vol_df = twse_volume(date_str)
    if vol_df.empty:
        return {}
    return {
        str(row["code"]).strip(): row["close"]
        for _, row in vol_df.iterrows()
        if row.get("close", 0) > 0
    }


def get_candidates(inst_df: pd.DataFrame, vol_df: pd.DataFrame) -> pd.DataFrame:
    if inst_df.empty:
        return pd.DataFrame()
    if not vol_df.empty:
        merged = inst_df.merge(vol_df, on="code", how="left")
    else:
        merged = inst_df.copy()
        merged["volume"] = 0.0
        merged["close"] = 0.0
    merged["inst_ratio"] = merged.apply(
        lambda r: (r["inst_net"] / r["volume"] * 100) if r.get("volume", 0) > 0 else 0,
        axis=1
    )
    return merged[merged["inst_ratio"] > 10].copy()


def screen_with_cache(candidates: pd.DataFrame, price_cache: dict,
                      current_cache: dict, hist_mode: bool) -> list:
    results = []
    for _, row in candidates.head(MAX_CANDIDATES).iterrows():
        code = str(row["code"]).strip()
        name = row.get("name", "")

        prices = price_cache.get(code, [])
        if len(prices) < 21:
            continue

        price_20d_ago = prices[-21]
        price_buy = prices[-1]

        if price_20d_ago <= 0 or price_buy <= 0:
            continue

        gain_20d = (price_buy - price_20d_ago) / price_20d_ago * 100
        if gain_20d < 30:
            continue

        if hist_mode:
            price_now = current_cache.get(code)
            if price_now and price_buy > 0:
                gain_future = (price_now - price_buy) / price_buy * 100
                passed = gain_future >= 15
                note = f"買入後20日 {'✅ 上漲' if passed else '❌ 未達'} {gain_future:.1f}%"
            else:
                price_now = None
                gain_future = None
                passed = None
                note = "❓ 無法取得現在收盤價"
        else:
            price_now = price_buy
            gain_future = None
            passed = None
            note = "⏳ 觀察中（今日新訊號）"

        print(f"  ✅ {code} {name}  近20日+{gain_20d:.1f}%  法人{row['inst_ratio']:.1f}%  {note}")

        results.append({
            "code": code,
            "name": name,
            "buy_price": round(price_buy, 2),
            "gain_20d": round(gain_20d, 2),
            "inst_net_shares": int(row["inst_net"]),
            "inst_ratio": round(row["inst_ratio"], 2),
            "volume_shares": int(row.get("volume", 0)),
            "price_now": round(price_now, 2) if price_now else None,
            "gain_future": round(gain_future, 2) if gain_future is not None else None,
            "passed": passed,
            "note": note,
        })
    return results


def run_screener(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = get_prev_trading_day()

    raw_hist = get_prev_trading_day(
        base_date=datetime.strptime(date_str, "%Y%m%d"), offset=20
    )

    print(f"\n=== 今日：{date_str} ===")
    print(f"=== 歷史基準（原始）：{raw_hist} ===")
    hist_date_str = find_valid_trading_day(raw_hist)
    print(f"=== 歷史基準（確認）：{hist_date_str} ===\n")

    all_stocks = []

    # ── 今日訊號 ──
    print(f"【今日訊號篩選 {date_str}】")
    inst_today = twse_institutional(date_str)
    vol_today = twse_volume(date_str)
    cands_today = get_candidates(inst_today, vol_today)
    print(f"  法人買超>10% 候選：{len(cands_today)} 檔，抓取歷史價格中...")
    codes_today = cands_today["code"].str.strip().tolist()
    cache_today = build_price_cache(date_str, codes_today)
    today_results = screen_with_cache(cands_today, cache_today, {}, hist_mode=False)
    print(f"今日符合條件：{len(today_results)} 檔\n")

    # ── 歷史回測 ──
    print(f"【歷史回測 {hist_date_str}】")
    inst_hist = twse_institutional(hist_date_str)
    vol_hist = twse_volume(hist_date_str)
    cands_hist = get_candidates(inst_hist, vol_hist)
    print(f"  法人買超>10% 候選：{len(cands_hist)} 檔，抓取歷史價格中...")
    codes_hist = cands_hist["code"].str.strip().tolist()
    cache_hist = build_price_cache(hist_date_str, codes_hist)
    current_cache = build_current_price_cache(date_str)
    hist_results = screen_with_cache(cands_hist, cache_hist, current_cache, hist_mode=True)
    print(f"歷史符合條件：{len(hist_results)} 檔\n")

    # ── 整合 ──
    for s in today_results:
        all_stocks.append({
            "code": s["code"], "name": s["name"], "market": "上市",
            "signal_date": date_str,
            "close": s["buy_price"],
            "gain_20d": s["gain_20d"],
            "inst_net_shares": s["inst_net_shares"],
            "inst_ratio": s["inst_ratio"],
            "volume_shares": s["volume_shares"],
            "backtest": {
                "buy_price": s["buy_price"],
                "price_after_20d": None,
                "date_after_20d": None,
                "gain_after_20d": None,
                "passed_15pct": None,
                "note": s["note"],
            }
        })

    for s in hist_results:
        all_stocks.append({
            "code": s["code"], "name": s["name"], "market": "上市",
            "signal_date": hist_date_str,
            "close": s["price_now"] or s["buy_price"],
            "gain_20d": s["gain_20d"],
            "inst_net_shares": s["inst_net_shares"],
            "inst_ratio": s["inst_ratio"],
            "volume_shares": s["volume_shares"],
            "backtest": {
                "buy_price": s["buy_price"],
                "price_after_20d": s["price_now"],
                "date_after_20d": date_str,
                "gain_after_20d": s["gain_future"],
                "passed_15pct": s["passed"],
                "note": s["note"],
            }
        })

    def sort_key(x):
        p = x["backtest"]["passed_15pct"]
        if p is True:   return (0, -x["gain_20d"])
        if p is None:   return (1, -x["gain_20d"])
        return (2, -x["gain_20d"])

    all_stocks.sort(key=sort_key)
    passed_count = len([s for s in all_stocks if s["backtest"]["passed_15pct"] is True])

    output = {
        "date": date_str,
        "hist_date": hist_date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "stocks": all_stocks,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 回測通過：{passed_count} 檔　共 {len(all_stocks)} 檔 → data/latest.json")
    return output


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_screener(date_arg)
