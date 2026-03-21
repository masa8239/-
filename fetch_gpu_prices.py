#!/usr/bin/env python3
"""
GPU価格スクレイパー for BENCHCORE
kakaku.com からGPU最安値を取得し、Googleスプレッドシート用CSVを生成します。

使い方:
    pip install requests beautifulsoup4
    python3 fetch_gpu_prices.py

出力:
    gpu_data.csv  ← GoogleスプレッドシートのGPUシート(gid=1)にインポート
"""

import csv
import time
import re
import sys

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    import requests
    HAS_BS4 = False
    print("警告: beautifulsoup4 未インストール。正規表現でパースします。")
    print("      pip install beautifulsoup4 でより安定した動作になります。\n")

# ========== GPU ベンチマーク・スペックデータ (固定値) ==========
# 3DMark Time Spy スコア、TDP(W)、VRAM、帯域幅は変わらないのでハードコード
GPU_SPECS = [
    {
        "GPU名": "GeForce RTX 5090",
        "3DMark Time Spy": 47487,
        "TDP": "575W",
        "VRAM": "32GB",
        "帯域幅": "1792GB/s",
        "kakaku_query": "RTX 5090",
    },
    {
        "GPU名": "GeForce RTX 5080",
        "3DMark Time Spy": 33200,
        "TDP": "360W",
        "VRAM": "16GB",
        "帯域幅": "960GB/s",
        "kakaku_query": "RTX 5080",
    },
    {
        "GPU名": "GeForce RTX 4090",
        "3DMark Time Spy": 36340,
        "TDP": "450W",
        "VRAM": "24GB",
        "帯域幅": "1008GB/s",
        "kakaku_query": "RTX 4090",
    },
    {
        "GPU名": "Radeon RX 9070 XT",
        "3DMark Time Spy": 30070,
        "TDP": "304W",
        "VRAM": "16GB",
        "帯域幅": "640GB/s",
        "kakaku_query": "RX 9070 XT",
    },
    {
        "GPU名": "Radeon RX 9070",
        "3DMark Time Spy": 25800,
        "TDP": "220W",
        "VRAM": "16GB",
        "帯域幅": "576GB/s",
        "kakaku_query": "RX 9070\"",
    },
    {
        "GPU名": "GeForce RTX 4080 SUPER",
        "3DMark Time Spy": 28531,
        "TDP": "320W",
        "VRAM": "16GB",
        "帯域幅": "736GB/s",
        "kakaku_query": "RTX 4080 SUPER",
    },
    {
        "GPU名": "Radeon RX 7900 XTX",
        "3DMark Time Spy": 34994,
        "TDP": "355W",
        "VRAM": "24GB",
        "帯域幅": "960GB/s",
        "kakaku_query": "RX 7900 XTX",
    },
    {
        "GPU名": "GeForce RTX 4070 Ti SUPER",
        "3DMark Time Spy": 26974,
        "TDP": "285W",
        "VRAM": "16GB",
        "帯域幅": "672GB/s",
        "kakaku_query": "RTX 4070 Ti SUPER",
    },
    {
        "GPU名": "Radeon RX 7900 XT",
        "3DMark Time Spy": 28938,
        "TDP": "315W",
        "VRAM": "20GB",
        "帯域幅": "800GB/s",
        "kakaku_query": "RX 7900 XT",
    },
    {
        "GPU名": "GeForce RTX 4070 SUPER",
        "3DMark Time Spy": 21130,
        "TDP": "220W",
        "VRAM": "12GB",
        "帯域幅": "504GB/s",
        "kakaku_query": "RTX 4070 SUPER",
    },
    {
        "GPU名": "GeForce RTX 4070",
        "3DMark Time Spy": 17021,
        "TDP": "200W",
        "VRAM": "12GB",
        "帯域幅": "504GB/s",
        "kakaku_query": "RTX 4070\"",
    },
    {
        "GPU名": "Radeon RX 7800 XT",
        "3DMark Time Spy": 18649,
        "TDP": "263W",
        "VRAM": "16GB",
        "帯域幅": "624GB/s",
        "kakaku_query": "RX 7800 XT",
    },
    {
        "GPU名": "GeForce RTX 4060 Ti",
        "3DMark Time Spy": 14502,
        "TDP": "160W",
        "VRAM": "16GB",
        "帯域幅": "288GB/s",
        "kakaku_query": "RTX 4060 Ti",
    },
    {
        "GPU名": "Radeon RX 7700 XT",
        "3DMark Time Spy": 14825,
        "TDP": "245W",
        "VRAM": "12GB",
        "帯域幅": "432GB/s",
        "kakaku_query": "RX 7700 XT",
    },
    {
        "GPU名": "GeForce RTX 4060",
        "3DMark Time Spy": 11043,
        "TDP": "115W",
        "VRAM": "8GB",
        "帯域幅": "272GB/s",
        "kakaku_query": "RTX 4060\"",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en;q=0.9",
}

KAKAKU_SEARCH_URL = "https://kakaku.com/search_results/?query={query}&act=Ks&category=0030"


def fetch_price_bs4(gpu_name: str, query: str) -> int:
    """BeautifulSoupを使ってkakaku.comから最安値を取得"""
    url = KAKAKU_SEARCH_URL.format(query=requests.utils.quote(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # 最安値候補を探す
        # 1) 検索結果の最初の商品の価格を取得
        price_tags = soup.select(".item_listitem .price, .itemListItem .price, .itmPrice")
        for tag in price_tags:
            text = tag.get_text(strip=True).replace(",", "").replace("円", "").replace("¥", "")
            m = re.search(r"(\d{4,7})", text)
            if m:
                return int(m.group(1))

        # 2) フォールバック: ページ内の価格っぽいパターン
        m = re.search(r"￥([\d,]+)", r.text)
        if m:
            return int(m.group(1).replace(",", ""))

    except Exception as e:
        print(f"  [警告] {gpu_name}: 取得失敗 ({e})")
    return 0


def fetch_price_regex(gpu_name: str, query: str) -> int:
    """正規表現でkakaku.comから最安値を取得（BeautifulSoup不使用）"""
    url = KAKAKU_SEARCH_URL.format(query=requests.utils.quote(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        html = r.text

        # ページ内の最初の価格パターンを探す
        patterns = [
            r'"price"[:\s]*"?([\d,]+)"?',         # JSON-like
            r'class="price[^"]*"[^>]*>.*?￥([\d,]+)',  # HTMLの価格タグ
            r'最安値[^￥]*￥([\d,]+)',
            r'￥([\d,]{5,8})',                      # ￥ + 5〜8桁
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                price_str = m.group(1).replace(",", "")
                price = int(price_str)
                if 5000 <= price <= 2000000:  # 5千〜200万の範囲
                    return price

    except Exception as e:
        print(f"  [警告] {gpu_name}: 取得失敗 ({e})")
    return 0


def fetch_price(gpu_name: str, query: str) -> int:
    if HAS_BS4:
        return fetch_price_bs4(gpu_name, query)
    return fetch_price_regex(gpu_name, query)


def calc_cospa(score: int, price: int) -> float:
    """コスパ = スコア ÷ 価格 × 1000（小数点2桁）"""
    if price <= 0:
        return 0.0
    return round(score / price * 1000, 2)


def main():
    print("=" * 60)
    print("BENCHCORE GPU価格スクレイパー")
    print("データソース: kakaku.com")
    print("=" * 60)
    print()

    results = []

    for i, gpu in enumerate(GPU_SPECS, 1):
        name = gpu["GPU名"]
        query = gpu["kakaku_query"]
        score = gpu["3DMark Time Spy"]

        print(f"[{i:2d}/{len(GPU_SPECS)}] {name} を検索中...", end=" ", flush=True)

        price = fetch_price(name, query)
        cospa = calc_cospa(score, price)

        if price > 0:
            print(f"¥{price:,}  (コスパ: {cospa})")
        else:
            print("価格取得失敗 (手動入力が必要)")

        results.append({
            "GPU名": name,
            "3DMark Time Spy": score,
            "TDP": gpu["TDP"],
            "VRAM": gpu["VRAM"],
            "帯域幅": gpu["帯域幅"],
            "コスパ": cospa,
            "価格(円)": price,
        })

        # レート制限: 1.5秒待機
        if i < len(GPU_SPECS):
            time.sleep(1.5)

    # CSV出力
    output_file = "gpu_data.csv"
    fieldnames = ["GPU名", "3DMark Time Spy", "TDP", "VRAM", "帯域幅", "コスパ", "価格(円)"]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print()
    print("=" * 60)
    print(f"完了! → {output_file} に保存しました")
    print()
    print("【次のステップ】")
    print("1. Googleスプレッドシートを開く")
    print("   https://docs.google.com/spreadsheets/d/e/2PACX-1vTWy_y9KV-3cBzUgvdzf6Ww_kzzw5nKopwJYhiSAgbHmjNrUR7q2BM9yMYNroIu_EyxWdBFCBufsv51/")
    print("2. 2枚目シート(GPU)を選択")
    print("3. ファイル → インポート → gpu_data.csv をアップロード")
    print("   「現在のシートを置換」を選択")
    print()
    print("または: gpu_data.csv の内容をシートに貼り付け")
    print("=" * 60)

    # 結果サマリー表示
    missing = [r["GPU名"] for r in results if r["価格(円)"] == 0]
    if missing:
        print()
        print(f"⚠️  価格未取得 ({len(missing)}件) — 手動で入力してください:")
        for m in missing:
            print(f"   - {m}")


if __name__ == "__main__":
    main()
