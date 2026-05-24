"""
台股三大法人選股篩選器（上市 + 上櫃合併版）
篩選條件：
  1. 法人淨買量 / 當日總成交量 > 10%
  2. 近20個交易日漲幅 > 30%
回測：符合條件當天收盤買入，20個交易日後是否再漲15%以上
資料來源：
  上市 — TWSE 公開資料 API
  上櫃 — TPEx OpenAPI
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


def get_prev_trading_day(base_date=None, offset=1) -> str:
    dt = base_date or datetime.today()
    days = 0
    skipped = 0
    while skipped < offset:
        days += 1
        candidate = dt - timedelta(days=days)
        if candidate.weekday() < 5:
            skipped += 1
    return candidate.strftime("%Y%m%d")


def to_roc_date(date_str: str) -> str:
    """YYYYMMDD → 民國年 YYY/MM/DD（TPEx 格式）"""
    dt = datetime.strptime(date_str, "%Y%m%d")
    roc_year = dt.year - 1911
    return f"{roc_year}/{dt.month:02d}/{dt.day:02d}"


def clean_num_int(s) -> int:
    try:
        return int(str(s).replace(",", "").replace("+", "").replace(" ", ""))
    except Exception:
        return 0


def clean_num_float(s) -> float:
    try:
        return float(str(s).replace(",", "").replace("+", "").replace(" ", ""))
    except Exception:
        return 0.0


# ══════════════════════════════════════════════
# 上市（TWSE）
# ══════════════════════════════════════════════

def twse_institutional(date_str: str) -> pd.DataFrame:
    """TWSE T86 三大法人買賣超"""
    url = (
        "https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?response=json&date={date_str}&selectType=ALL"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[TWSE inst] 失敗: {e}")
        return pd.DataFrame()

    if data.get("stat") != "OK":
        print(f"[TWSE inst] stat={data.get('stat')}")
        return pd.DataFrame()

    df = pd.DataFrame(data["data"], columns=data["fields"])
    df = df.rename(columns={"證券代號": "code", "證券名稱": "name", "三大法人買賣超股數": "inst_net"})
    df["inst_net"] = df["inst_net"].apply(clean_num_int)
    df["market"] = "上市"
    return df[["code", "name", "inst_net", "market"]].copy()


def twse_volume(date_str: str) -> pd.DataFrame:
    """TWSE STOCK_DAY_ALL 成交量與收盤價"""
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL"
        f"?response=json&date={date_str}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[TWSE vol] 失敗: {e}")
        return pd.DataFrame()

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
    keep = [c for c in ["code", "volume", "close"] if c in df.columns]
    df = df[keep].copy()
    if "volume" in df.columns:
        df["volume"] = df["volume"].apply(clean_num_float)
    if "close" in df.columns:
        df["close"] = df["close"].apply(clean_num_float)
    return df


def twse_price_history(stock_code: str, date_str: str) -> list:
    """TWSE 個股近兩個月收盤價"""
    prices = []
    for offset in [1, 0]:
        ym = (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=30 * offset)).strftime("%Y%m01")
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


def twse_price_on_date(stock_code: str, target_date_str: str) -> float | None:
    """TWSE 取得指定日期收盤價"""
    target_dt = datetime.strptime(target_date_str, "%Y%m%d")
    ym = target_dt.strftime("%Y%m01")
    url = (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
        f"?response=json&date={ym}&stockNo={stock_code}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if data.get("stat") == "OK":
            all_prices = []
            for row in data.get("data", []):
                try:
                    roc = row[0].strip().split("/")
                    row_dt = datetime(int(roc[0]) + 1911, int(roc[1]), int(roc[2]))
                    close = float(row[6].replace(",", ""))
                    all_prices.append((row_dt, close))
                except Exception:
                    pass
            candidates = [(dt, p) for dt, p in all_prices if dt <= target_dt]
            if candidates:
                return sorted(candidates, key=lambda x: x[0])[-1][1]
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════
# 上櫃（TPEx）
# ══════════════════════════════════════════════

def tpex_institutional(date_str: str) -> pd.DataFrame:
    """TPEx 上櫃三大法人買賣超"""
    roc = to_roc_date(date_str)
    url = f"https://www.tpex.org.tw/openapi/v1/tpex_esb_dei_buy_sell?date={roc}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[TPEx inst] 失敗: {e}")
        return pd.DataFrame()

    if not data or not isinstance(data, list):
        print(f"[TPEx inst] 無資料, date={date_str}")
        return pd.DataFrame()

    rows = []
    for item in data:
        try:
            code = str(item.get("SecuritiesCompanyCode", "")).strip()
            name = str(item.get("CompanyName", "")).strip()
            # 三大法人合計 = 外資 + 投信 + 自營商
            foreign = clean_num_int(item.get("ForeignInvestmentNetBuySell", 0))
            trust = clean_num_int(item.get("InvestmentTrustNetBuySell", 0))
            dealer = clean_num_int(item.get("DealerNetBuySell", 0))
            inst_net = foreign + trust + dealer
            rows.append({"code": code, "name": name, "inst_net": inst_net})
        except Exception:
            pass

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["market"] = "上櫃"
    return df[["code", "name", "inst_net", "market"]].copy()


def tpex_volume(date_str: str) -> pd.DataFrame:
    """TPEx 上櫃每日收盤行情"""
    roc = to_roc_date(date_str)
    url = f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?date={roc}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
    except Exception as e:
        print(f"[TPEx vol] 失敗: {e}")
        return pd.DataFrame()

    if not data or not isinstance(data, list):
        return pd.DataFrame()

    rows = []
    for item in data:
        try:
            code = str(item.get("SecuritiesCompanyCode", "")).strip()
            volume = clean_num_float(item.get("TradingShares", 0))
            close = clean_num_float(item.get("ClosingPrice", 0))
            rows.append({"code": code, "volume": volume, "close": close})
        except Exception:
            pass

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def tpex_price_history(stock_code: str, date_str: str) -> list:
    """TPEx 個股近兩個月收盤價"""
    prices = []
    for offset in [1, 0]:
        dt = datetime.strptime(date_str, "%Y%m%d") - timedelta(days=30 * offset)
        roc_ym = f"{dt.year - 1911}/{dt.month:02d}/01"
        url = (
            f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_monthly_transaction_statistics"
            f"?date={roc_ym}&code={stock_code}"
        )
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            data = r.json()
            if isinstance(data, list):
                for item in data:
                    try:
                        close = clean_num_float(item.get("ClosingPrice", 0))
                        if close > 0:
                            prices.append(close)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(0.3)
    return prices


def tpex_price_on_date(stock_code: str, target_date_str: str) -> float | None:
    """TPEx 取得指定日期收盤價"""
    target_dt = datetime.strptime(target_date_str, "%Y%m%d")
    roc_ym = f"{target_dt.year - 1911}/{target_dt.month:02d}/01"
    url = (
        f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_monthly_transaction_statistics"
        f"?date={roc_ym}&code={stock_code}"
    )
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        if isinstance(data, list) and data:
            closes = [clean_num_float(item.get("ClosingPrice", 0)) for item in data]
            closes = [c for c in closes if c > 0]
            if closes:
                return closes[-1]
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════
# 合併篩選邏輯
# ══════════════════════════════════════════════

def screen_one_day(date_str: str) -> list:
    """對指定日期執行上市+上櫃合併篩選"""

    # ── 上市 ──
    print(f"  抓取上市資料...")
    twse_inst = twse_institutional(date_str)
    twse_vol = twse_volume(date_str)
    time.sleep(0.5)

    # ── 上櫃 ──
    print(f"  抓取上櫃資料...")
    tpex_inst = tpex_institutional(date_str)
    tpex_vol = tpex_volume(date_str)
    time.sleep(0.5)

    results = []

    for inst_df, vol_df, price_fn in [
        (twse_inst, twse_vol, twse_price_history),
        (tpex_inst, tpex_vol, tpex_price_history),
    ]:
        if inst_df.empty:
            continue

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
        market = inst_df["market"].iloc[0] if not inst_df.empty else ""
        print(f"  [{market}] 法人買超>10% 候選：{len(candidates)} 檔")

        for _, row in candidates.iterrows():
            code = row["code"].strip()
            name = row.get("name", "")
            market = row.get("market", "")
            time.sleep(0.4)

            prices = price_fn(code, date_str)
            if len(prices) < 21:
                continue

            price_20d_ago = prices[-21]
            price_buy = prices[-1]

            if price_20d_ago <= 0:
                continue

            gain_20d = (price_buy - price_20d_ago) / price_20d_ago * 100

            if gain_20d >= 30:
                results.append({
                    "code": code,
                    "name": name,
                    "market": market,
                    "buy_price": round(price_buy, 2),
                    "gain_20d": round(gain_20d, 2),
                    "inst_net_shares": int(row["inst_net"]),
                    "inst_ratio": round(row["inst_ratio"], 2),
                    "volume_shares": int(row.get("volume", 0)),
                })
                print(f"  ✅ [{market}] {code} {name}  近20日 +{gain_20d:.1f}%  法人占比 {row['inst_ratio']:.1f}%")

    return results


# ══════════════════════════════════════════════
# 主程式
# ══════════════════════════════════════════════

def run_screener(date_str: str | None = None) -> dict:
    if date_str is None:
        date_str = get_prev_trading_day()

    print(f"\n=== 執行日期：{date_str} ===")

    print(f"\n【今日訊號篩選】")
    today_signals = screen_one_day(date_str)
    print(f"今日符合條件：{len(today_signals)} 檔")

    today_stocks = []
    for s in today_signals:
        today_stocks.append({
            "code": s["code"],
            "name": s["name"],
            "market": s["market"],
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
                "note": "⏳ 觀察中（今日新訊號）",
            }
        })

    # ── 回測：20交易日前的訊號 ──
    hist_date_str = get_prev_trading_day(
        base_date=datetime.strptime(date_str, "%Y%m%d"), offset=20
    )
    print(f"\n【歷史回測：{hist_date_str}（20交易日前）的訊號】")
    hist_signals = screen_one_day(hist_date_str)
    print(f"歷史符合條件：{len(hist_signals)} 檔")

    hist_stocks = []
    for s in hist_signals:
        code = s["code"]
        market = s["market"]
        time.sleep(0.4)

        if market == "上市":
            price_now = twse_price_on_date(code, date_str)
        else:
            price_now = tpex_price_on_date(code, date_str)

        if price_now is None:
            gain_future = None
            passed = None
            note = "❓ 無法取得現在收盤價"
        else:
            gain_future = (price_now - s["buy_price"]) / s["buy_price"] * 100
            passed = gain_future >= 15
            note = f"買入後20日 {'✅ 上漲' if passed else '❌ 未達'} {gain_future:.1f}%"

        print(f"  [{market}] {code} {s['name']}  買入:{s['buy_price']}→現價:{price_now}  {note}")

        hist_stocks.append({
            "code": code,
            "name": s["name"],
            "market": market,
            "signal_date": hist_date_str,
            "close": price_now or s["buy_price"],
            "gain_20d": s["gain_20d"],
            "inst_net_shares": s["inst_net_shares"],
            "inst_ratio": s["inst_ratio"],
            "volume_shares": s["volume_shares"],
            "backtest": {
                "buy_price": s["buy_price"],
                "price_after_20d": round(price_now, 2) if price_now else None,
                "date_after_20d": date_str,
                "gain_after_20d": round(gain_future, 2) if gain_future is not None else None,
                "passed_15pct": passed,
                "note": note,
            }
        })

    def sort_key(x):
        p = x["backtest"]["passed_15pct"]
        if p is True:
            return (0, -x["gain_20d"])
        if p is None:
            return (1, -x["gain_20d"])
        return (2, -x["gain_20d"])

    all_stocks = sorted(hist_stocks + today_stocks, key=sort_key)
    passed_count = len([s for s in all_stocks if s["backtest"]["passed_15pct"] is True])

    output = {
        "date": date_str,
        "hist_date": hist_date_str,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "ok",
        "stocks": all_stocks,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 回測通過（漲幅≥15%）：{passed_count} 檔")
    print(f"📊 共 {len(all_stocks)} 檔 → data/latest.json")
    return output


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_screener(date_arg)
