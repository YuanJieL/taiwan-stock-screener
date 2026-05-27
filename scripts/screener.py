"""
台股三大法人選股篩選器（AI 法人戰情室版）
篩選條件：
  1. 法人淨買量 / 當日總成交量 > 10%
  2. 近20個交易日漲幅 > 30%
  3. 排除 ETF（含槓桿/反向）
新增：AI 評分、多空燈號、回測統計
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

ETF_NAME_KEYWORDS = ["ETF","正二","反一","反向","槓桿","基金",
                     "高股息","ESG","永續","債券","期貨","商品"]


def is_etf(code: str, name: str) -> bool:
    if len(str(code).strip()) > 4:
        return True
    return any(kw in str(name) for kw in ETF_NAME_KEYWORDS)


def calc_ai_score(inst_ratio: float, gain_20d: float, gain_future: float | None) -> float:
    """
    AI 多因子評分（0~100）
    法人強度 40% + 趨勢動能 40% + 回測績效 20%
    """
    # 法人強度（上限 50%占比 → 滿分）
    inst_score = min(inst_ratio / 50 * 40, 40)
    # 趨勢動能（上限 150%漲幅 → 滿分）
    trend_score = min(gain_20d / 150 * 40, 40)
    # 回測績效
    if gain_future is None:
        perf_score = 10  # 觀察中給基礎分
    elif gain_future >= 30:
        perf_score = 20
    elif gain_future >= 15:
        perf_score = 15
    elif gain_future >= 0:
        perf_score = 8
    else:
        perf_score = 0
    return round(inst_score + trend_score + perf_score, 1)


def calc_signal(ai_score: float, passed: bool | None) -> str:
    """多空燈號"""
    if passed is True and ai_score >= 70:
        return "🟢 強力買進"
    if passed is True and ai_score >= 50:
        return "🟢 買進"
    if passed is None and ai_score >= 60:
        return "🟡 強力觀察"
    if passed is None:
        return "🟡 觀察"
    if passed is False and ai_score >= 50:
        return "🟠 留意"
    return "🔴 迴避"


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
    candidates = merged[merged["inst_ratio"] > 10].copy()
    before = len(candidates)
    candidates = candidates[
        ~candidates.apply(lambda r: is_etf(r["code"], r.get("name", "")), axis=1)
    ].copy()
    etf_removed = before - len(candidates)
    if etf_removed > 0:
        print(f"  已過濾 ETF/槓桿商品：{etf_removed} 檔")
    return candidates


def screen_with_cache(candidates: pd.DataFrame, price_cache: dict,
                      current_cache: dict, hist_mode: bool) -> list:
    results = []
    for _, row in candidates.iterrows():
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

        ai_score = calc_ai_score(row["inst_ratio"], gain_20d, gain_future)
        signal = calc_signal(ai_score, passed)

        print(f"  ✅ {code} {name}  近20日+{gain_20d:.1f}%  法人{row['inst_ratio']:.1f}%  AI:{ai_score}  {signal}")

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
            "ai_score": ai_score,
            "signal": signal,
        })
    return results


def calc_backtest_stats(hist_results: list) -> dict:
    """計算回測統計：勝率、平均報酬、最大回撤、最大漲幅"""
    gains = [s["gain_future"] for s in hist_results if s["gain_future"] is not None]
    if not gains:
        return {
            "win_rate": None,
            "avg_return": None,
            "max_drawdown": None,
            "max_gain": None,
            "total": 0,
            "passed": 0,
        }
    passed = sum(1 for g in gains if g >= 15)
    return {
        "win_rate": round(passed / len(gains) * 100, 1),
        "avg_return": round(sum(gains) / len(gains), 1),
        "max_drawdown": round(min(gains), 1),
        "max_gain": round(max(gains), 1),
        "total": len(gains),
        "passed": passed,
    }


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
    print(f"  法人買超>10%（排除ETF後）候選：{len(cands_today)} 檔，抓取歷史價格中...")
    codes_today = cands_today["code"].str.strip().tolist() if not cands_today.empty else []
    cache_today = build_price_cache(date_str, codes_today)
    today_results = screen_with_cache(cands_today, cache_today, {}, hist_mode=False)
    print(f"今日符合條件：{len(today_results)} 檔\n")

    # ── 歷史回測 ──
    print(f"【歷史回測 {hist_date_str}】")
    inst_hist = twse_institutional(hist_date_str)
    if inst_hist.empty:
        hist_date_str = find_valid_trading_day(hist_date_str)
        inst_hist = twse_institutional(hist_date_str)
    vol_hist = twse_volume(hist_date_str)
    cands_hist = get_candidates(inst_hist, vol_hist)
    print(f"  法人買超>10%（排除ETF後）候選：{len(cands_hist)} 檔，抓取歷史價格中...")

    if cands_hist.empty:
        hist_results = []
    else:
        codes_hist = cands_hist["code"].str.strip().tolist()
        cache_hist = build_price_cache(hist_date_str, codes_hist)
        current_cache = build_current_price_cache(date_str)
        hist_results = screen_with_cache(cands_hist, cache_hist, current_cache, hist_mode=True)

    print(f"歷史符合條件：{len(hist_results)} 檔\n")

    # ── 回測統計 ──
    stats = calc_backtest_stats(hist_results)
    print(f"📊 回測統計：勝率 {stats['win_rate']}%  平均報酬 {stats['avg_return']}%  "
          f"最大回撤 {stats['max_drawdown']}%  最大漲幅 {stats['max_gain']}%")

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
            "ai_score": s["ai_score"],
            "signal": s["signal"],
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
            "ai_score": s["ai_score"],
            "signal": s["signal"],
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
        if p is True:  return (0, -x["ai_score"])
        if p is None:  return (1, -x["ai_score"])
        return (2, -x["ai_score"])

    all_stocks.sort(key=sort_key)

    output = {
        "date": date_str,
        "hist_date": hist_date_str,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "backtest_stats": stats,
        "stocks": all_stocks,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 回測通過：{stats['passed']} 檔　共 {len(all_stocks)} 檔 → data/latest.json")
    return output


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_screener(date_arg)