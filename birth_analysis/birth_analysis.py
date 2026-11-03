"""
대한민국 출생아수·합계출산율·자연증가 데이터 클렌징 및 다각도 분석 (pandas)

원본: KOSIS 「인구동향조사」 (통계표 ID: INH_1B8000F_01), 1970~2025
사용법: python birth_analysis.py [엑셀파일경로]
"""

import re
import sys
from pathlib import Path

import pandas as pd

DEFAULT_XLSX = Path(
    r"C:\Users\user\Downloads\생산성본부_바이브코딩수업\DataSet"
    r"\출생아수__합계출산율__자연증가_등_20260605082440.xlsx"
)
OUT_DIR = Path(__file__).resolve().parent / "output"

# 원본 행 이름 -> 분석용 컬럼명
COLUMN_MAP = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가건수",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 20)
pd.set_option("display.float_format", lambda v: f"{v:,.3f}")


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n {title}\n{'=' * 70}")


# ----------------------------------------------------------------------
# 1. 데이터 클렌징
# ----------------------------------------------------------------------
def load_and_clean(xlsx_path: Path) -> pd.DataFrame:
    section("1. 데이터 클렌징")

    # '데이터' 시트만 읽는다 ('메타정보' 시트는 출처/주석)
    raw = pd.read_excel(xlsx_path, sheet_name="데이터", header=None)
    print(f"[원본] shape={raw.shape} (행=지표, 열=연도인 가로형 구조)")

    # (1) 첫 행 = 연도 헤더, 첫 열 = 지표명 → 전치(transpose)해서 세로형(연도별 행)으로 변환
    raw = raw.set_index(0)
    raw.index = raw.index.astype(str).str.strip()
    year_header = raw.iloc[0]
    df = raw.iloc[1:].T
    df.columns.name = None
    df.insert(0, "연도_원본", year_header.values)

    # (2) 연도 정리: '2025 p)' 같은 잠정치 표기 분리 → 정수 연도 + 잠정치 플래그
    year_str = df["연도_원본"].astype(str).str.strip()
    df["잠정치"] = year_str.str.contains(r"p\)", regex=True)
    df["연도"] = year_str.str.extract(r"(\d{4})", expand=False).astype(int)
    print(f"[연도] 잠정치 연도: {df.loc[df['잠정치'], '연도'].tolist()}")

    # (3) 컬럼명 정리 (단위 표기 제거)
    df = df.rename(columns=COLUMN_MAP)
    df = df[["연도", "잠정치", *COLUMN_MAP.values()]]

    # (4) 숫자형 변환: 콤마, '-', 공백 등 비숫자 → NaN
    for col in COLUMN_MAP.values():
        cleaned = df[col].astype(str).str.replace(",", "").str.strip()
        cleaned = cleaned.replace({"-": None, "": None, "nan": None, "…": None})
        df[col] = pd.to_numeric(cleaned, errors="coerce")
    df["출생아수"] = df["출생아수"].astype("Int64")
    df["자연증가건수"] = df["자연증가건수"].astype("Int64")

    # (5) 결측치 / 중복 점검
    na = df.isna().sum()
    print(f"[결측치] 총 {int(na.sum())}개" + ("" if na.sum() == 0 else f"\n{na[na > 0]}"))
    dup = df["연도"].duplicated().sum()
    print(f"[중복 연도] {dup}개")
    df = df.drop_duplicates(subset="연도").sort_values("연도").reset_index(drop=True)

    # (6) 연도 연속성 점검
    missing_years = sorted(set(range(df["연도"].min(), df["연도"].max() + 1)) - set(df["연도"]))
    print(f"[연도 범위] {df['연도'].min()}~{df['연도'].max()}, 누락 연도: {missing_years or '없음'}")

    # (7) 값 범위 검증 (상식적인 범위를 벗어나면 경고)
    checks = {
        "출생아수": (0, 2_000_000),
        "합계출산율": (0, 10),
        "출생성비": (90, 130),
        "조출생률": (0, 60),
    }
    for col, (lo, hi) in checks.items():
        bad = df[(df[col] < lo) | (df[col] > hi)]
        print(f"[범위 검증] {col} ∈ [{lo}, {hi}] → 이상치 {len(bad)}건")

    # (8) 파생 변수
    df["연대"] = (df["연도"] // 10 * 10).astype(str) + "년대"
    df["출생아수_증감"] = df["출생아수"].diff()
    df["출생아수_증감률(%)"] = (df["출생아수"].astype(float).pct_change() * 100).round(2)
    df["출생아수_5년이동평균"] = df["출생아수"].astype(float).rolling(5).mean().round(0)
    df["출생아수_1970대비(%)"] = (df["출생아수"] / df["출생아수"].iloc[0] * 100).astype(float).round(1)
    df["사망자수_추정"] = df["출생아수"] - df["자연증가건수"]  # 자연증가 = 출생 - 사망

    print("\n[정제 결과 미리보기]")
    print(df[["연도", "잠정치", *COLUMN_MAP.values()]].head().to_string(index=False))
    print("...")
    print(df[["연도", "잠정치", *COLUMN_MAP.values()]].tail().to_string(index=False))
    print(f"\n[dtypes]\n{df.dtypes.to_string()}")
    return df


# ----------------------------------------------------------------------
# 2. 다각도 분석
# ----------------------------------------------------------------------
def analyze(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    births = df.set_index("연도")["출생아수"].astype(float)

    # 2-1 기술통계
    section("2-1. 기술통계")
    desc = df[list(COLUMN_MAP.values())].astype(float).describe().T
    print(desc.to_string())
    results["기술통계"] = desc

    # 2-2 최고/최저 시점
    section("2-2. 지표별 최고·최저 연도")
    rows = []
    for col in COLUMN_MAP.values():
        s = df.set_index("연도")[col].astype(float)
        rows.append({"지표": col, "최고연도": s.idxmax(), "최고값": s.max(),
                     "최저연도": s.idxmin(), "최저값": s.min()})
    extremes = pd.DataFrame(rows)
    print(extremes.to_string(index=False))
    results["최고최저"] = extremes

    # 2-3 연대별 평균
    section("2-3. 연대별 평균")
    decade = df.groupby("연대")[list(COLUMN_MAP.values())].mean()
    decade["출생아수"] = decade["출생아수"].round(0)
    print(decade.to_string())
    results["연대별평균"] = decade

    # 2-4 전년 대비 증감 Top 5
    section("2-4. 출생아수 전년 대비 증감 Top 5")
    yoy = df[["연도", "출생아수", "출생아수_증감", "출생아수_증감률(%)"]].dropna()
    print("▼ 감소폭 Top 5 (명)")
    print(yoy.nsmallest(5, "출생아수_증감").to_string(index=False))
    print("\n▲ 증가폭 Top 5 (명)")
    print(yoy.nlargest(5, "출생아수_증감").to_string(index=False))
    results["전년대비증감"] = yoy

    # 2-5 주요 이정표 (처음으로 기준선 아래로 내려간 해)
    section("2-5. 주요 이정표")

    def first_year(mask: pd.Series) -> str:
        hit = df.loc[mask, "연도"]
        return str(hit.iloc[0]) if len(hit) else "-"

    milestones = pd.DataFrame([
        ("출생아수 100만 명 미만", first_year(df["출생아수"] < 1_000_000)),
        ("출생아수 50만 명 미만", first_year(df["출생아수"] < 500_000)),
        ("출생아수 40만 명 미만", first_year(df["출생아수"] < 400_000)),
        ("출생아수 30만 명 미만", first_year(df["출생아수"] < 300_000)),
        ("합계출산율 2.1명 미만 (인구대체수준)", first_year(df["합계출산율"] < 2.1)),
        ("합계출산율 1.3명 미만 (초저출산)", first_year(df["합계출산율"] < 1.3)),
        ("합계출산율 1.0명 미만", first_year(df["합계출산율"] < 1.0)),
        ("자연증가 마이너스 전환 (데드크로스)", first_year(df["자연증가건수"] < 0)),
    ], columns=["이정표", "최초 연도"])
    print(milestones.to_string(index=False))
    results["이정표"] = milestones

    # 2-6 구간별 연평균 증감률 (CAGR)
    section("2-6. 구간별 출생아수 연평균 증감률 (CAGR)")
    periods = [(1970, 1983), (1983, 2000), (2000, 2015), (2015, 2023), (2023, 2025), (1970, 2025)]
    cagr = pd.DataFrame([
        {"구간": f"{a}→{b}", "시작": births[a], "종료": births[b],
         "CAGR(%)": ((births[b] / births[a]) ** (1 / (b - a)) - 1) * 100}
        for a, b in periods
    ])
    print(cagr.to_string(index=False))
    results["CAGR"] = cagr

    # 2-7 상관관계
    section("2-7. 지표 간 상관계수 (Pearson)")
    corr = df[list(COLUMN_MAP.values())].astype(float).corr()
    print(corr.round(3).to_string())
    results["상관계수"] = corr

    # 2-8 출생성비 추이 (남아선호 시기)
    section("2-8. 출생성비 (여아 100명당 남아) — 자연 수준 103~107 대비")
    sr = df[["연도", "출생성비"]]
    print(f"정상범위(103~107) 초과 연도 수: {(sr['출생성비'] > 107).sum()}")
    print(sr[sr["출생성비"] > 110].to_string(index=False))
    results["출생성비_이상"] = sr[sr["출생성비"] > 107]

    # 2-9 최근 10년 추세 및 반등 여부
    section("2-9. 최근 10년 (2016~2025)")
    recent = df[df["연도"] >= 2016][["연도", "잠정치", "출생아수", "출생아수_증감률(%)",
                                     "합계출산율", "자연증가건수"]]
    print(recent.to_string(index=False))
    trough = int(births.idxmin())
    print(f"\n→ 출생아수 최저점은 {trough}년({births.min():,.0f}명), "
          f"이후 2025년(잠정)까지 {births[2025] - births.min():+,.0f}명 "
          f"({(births[2025] / births.min() - 1) * 100:+.1f}%) 반등")
    results["최근10년"] = recent

    # 2-10 요약
    section("2-10. 핵심 요약")
    peak_y = int(births.idxmax())
    print(f"- 출생아수 최고: {peak_y}년 {births.max():,.0f}명 → 최저: {trough}년 {births.min():,.0f}명 "
          f"({(births.min() / births.max() - 1) * 100:.1f}%)")
    print(f"- 1970년 대비 2025년 출생아수: {births[2025] / births[1970] * 100:.1f}% 수준")
    tfr = df.set_index("연도")["합계출산율"]
    print(f"- 합계출산율: 1970년 {tfr[1970]:.2f}명 → 최저 {tfr.idxmin()}년 {tfr.min():.2f}명 → 2025년(잠정) {tfr[2025]:.2f}명")
    print(f"- 자연증가 마이너스 전환: {milestones.iloc[7, 1]}년부터 사망자수가 출생아수를 초과")

    return results


def save_excel(df: pd.DataFrame, results: dict[str, pd.DataFrame], path: Path) -> None:
    """정제 데이터와 분석표를 시트별로 하나의 엑셀 파일에 저장"""
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="정제데이터", index=False)
        for name, table in results.items():
            table.to_excel(writer, sheet_name=name[:31])


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    df = load_and_clean(xlsx)
    results = analyze(df)

    OUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUT_DIR / "births_clean.csv", index=False, encoding="utf-8-sig")
    save_excel(df, results, OUT_DIR / "births_analysis.xlsx")
    print(f"\n[저장] {OUT_DIR / 'births_clean.csv'}\n[저장] {OUT_DIR / 'births_analysis.xlsx'}")


if __name__ == "__main__":
    main()
