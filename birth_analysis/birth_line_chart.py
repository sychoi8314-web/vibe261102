"""
대한민국 출생아수 추이 라인 그래프 (1970~2025)

birth_analysis.py 의 클렌징 함수를 재사용한다.
plot_births_line() 은 GUI(birth_analysis_gui.py)에서도 그대로 사용한다.
사용법: python birth_line_chart.py [엑셀파일경로]
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
from matplotlib.figure import Figure

from birth_analysis import DEFAULT_XLSX, OUT_DIR, load_and_clean

# 한글 폰트 (Windows: 맑은 고딕) + 마이너스 기호 깨짐 방지
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

LINE = "#2a78d6"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"


def plot_births_line(fig: Figure, df: pd.DataFrame, start: int = 1970, end: int = 2025) -> None:
    """정제된 df 로 start~end 구간의 출생아수 라인 그래프를 fig 에 그린다."""
    fig.clear()
    fig.set_facecolor(SURFACE)
    ax = fig.add_subplot(111)
    ax.set_facecolor(SURFACE)

    df = df[(df["연도"] >= start) & (df["연도"] <= end)].reset_index(drop=True)
    years = df["연도"]
    births = df["출생아수"].astype(float) / 10_000  # 만 명 단위

    # 확정치는 실선, 잠정치 구간(마지막 확정 연도 → 잠정 연도)은 점선
    final = ~df["잠정치"]
    ax.plot(years[final], births[final], color=LINE, linewidth=2)
    if df["잠정치"].any():
        prov = df.index[df["잠정치"]]
        seg = prov.insert(0, prov[0] - 1) if prov[0] > 0 else prov
        ax.plot(years[seg], births[seg], color=LINE, linewidth=2, linestyle="--")

    # 선택적 직접 라벨: 최고, 최저, 마지막 연도 (같은 연도면 하나로 합침)
    def label(year: int, text: str, dx: int, dy: float, ha: str = "center") -> None:
        y = births[years == year].iloc[0]
        ax.scatter([year], [y], s=36, color=LINE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.annotate(text, (year, y), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, fontsize=10, color=TEXT,
                    arrowprops=dict(arrowstyle="-", color=TEXT_2, lw=0.8))

    def value(year: int) -> str:
        return f"{births[years == year].iloc[0]:.1f}만 명"

    peak_y = int(years[births.idxmax()])
    low_y = int(years[births.idxmin()])
    last_y = int(years.iloc[-1])
    last_tag = f"{last_y}년" + ("(잠정)" if df["잠정치"].iloc[-1] else "")
    if peak_y != last_y:
        label(peak_y, f"{peak_y}년 최고\n{value(peak_y)}", 30, 10, "left")
    if low_y != last_y:
        label(low_y, f"{low_y}년 최저\n{value(low_y)}", -10, -45, "right")
    label(last_y, f"{last_tag}\n{value(last_y)}", 0, 35)

    # 기준선: 50만 명
    ax.axhline(50, color=TEXT_2, linewidth=0.8, linestyle=":")
    ax.text(start + 0.5, 51.5, "50만 명", fontsize=9, color=TEXT_2)

    ax.set_title(f"대한민국 연도별 출생아수 ({start}~{end})", fontsize=15, color=TEXT,
                 loc="left", pad=14, fontweight="bold")
    ax.set_xlabel("연도", color=TEXT_2)
    ax.set_ylabel("출생아수 (만 명)", color=TEXT_2)
    ax.set_xlim(start - 1, end + 1)
    ax.set_ylim(0, 115)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(5 if end - start > 15 else 1))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(20))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.tick_params(colors=TEXT_2, length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    note = " · 잠정치는 점선" if df["잠정치"].any() else ""
    fig.text(0.01, 0.01, f"자료: 통계청 KOSIS 「인구동향조사」{note}", fontsize=9, color=TEXT_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    df = load_and_clean(xlsx)

    fig = plt.figure(figsize=(12, 6))
    plot_births_line(fig, df, 1970, 2025)

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "births_line_1970_2025.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(f"\n[저장] {out}")
    plt.show()


if __name__ == "__main__":
    main()
