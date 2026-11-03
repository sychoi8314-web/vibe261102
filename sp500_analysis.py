"""
S&P 500 과거 데이터 분석 GUI 앱 (PyQt6 + Pandas + Matplotlib)

1) CSV를 불러와 클렌징하고 (날짜/콤마/% 변환, 빈 거래량 제거, OHLC 오류 보정)
2) Pandas로 다각도 분석을 하고 (기술통계, 연도별 성과, 낙폭, 극단값, 계절성, 이동평균)
3) 지정한 기간(기본 2000.01 ~ 2019.12)의 종가 라인그래프와 분석 차트를 앱 안에 그립니다.

설치: pip install PyQt6 pandas numpy matplotlib
실행: python sp500_analysis.py [CSV 경로]
"""

import contextlib
import io
import sys
from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
import matplotlib
from PyQt6.QtCore import QAbstractTableModel, QDate, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

DEFAULT_PATH = r"C:\Users\user\Downloads\생산성본부_바이브코딩수업\DataSet\S&P 500 과거 데이터.csv"

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False
pd.set_option("display.width", 140)
pd.set_option("display.float_format", "{:,.2f}".format)


# ─────────────────────────────────────────────
# 1. 데이터 클렌징
# ─────────────────────────────────────────────
def load_and_clean(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    print(f"[원본] {raw.shape[0]:,}행 × {raw.shape[1]}열, 컬럼: {list(raw.columns)}")

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "ChangePct",
    })

    # 날짜: "2019- 11- 14" 처럼 공백이 섞인 형식 → 공백 제거 후 datetime 변환
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", "", regex=False),
                                format="%Y-%m-%d", errors="coerce")

    # 가격: 천 단위 콤마 제거 → float
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce")

    # 변동 %: "%" 제거 → float (단위: %)
    df["ChangePct"] = pd.to_numeric(df["ChangePct"].str.replace("%", "", regex=False),
                                    errors="coerce")

    # 거래량: 전부 비어 있으면 분석 의미가 없으므로 제거
    vol = df["Volume"].replace("", np.nan)
    if vol.isna().all():
        print("[클렌징] 거래량 컬럼이 전부 비어 있어 제거")
        df = df.drop(columns="Volume")

    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    print(f"[클렌징] 날짜/종가 결측 제거: {before - len(df)}행")

    before = len(df)
    df = df.drop_duplicates(subset="Date", keep="first")
    print(f"[클렌징] 중복 날짜 제거: {before - len(df)}행")

    # 가격이 0 이하인 행은 명백한 오류이므로 제거
    before = len(df)
    df = df[(df[["Open", "High", "Low", "Close"]] > 0).all(axis=1)]
    print(f"[클렌징] 0 이하 가격 제거: {before - len(df)}행")

    # 논리 오류: 고가 < max(시가, 종가) 또는 저가 > min(시가, 종가)
    # 종가는 정상이므로 행을 지우지 않고 고가/저가를 보정 (예: 2001-10-17 시가 1107.6 > 고가 1107.1)
    ohlc = df[["Open", "High", "Low", "Close"]]
    bad = (df["High"] < ohlc.max(axis=1)) | (df["Low"] > ohlc.min(axis=1))
    for d in df.index[bad]:
        print(f"[클렌징] OHLC 논리 오류 보정: {df.at[d, 'Date']:%Y-%m-%d}")
    df["High"] = ohlc.max(axis=1)
    df["Low"] = ohlc.min(axis=1)

    # 최신→과거 순서로 되어 있으므로 시간 오름차순 정렬 후 인덱스로 지정
    df = df.sort_values("Date").set_index("Date")

    # 변동 %는 원본 값 대신 정렬된 종가로 재계산해 검증
    recalc = df["Close"].pct_change() * 100
    diff = (recalc - df["ChangePct"]).abs()
    print(f"[검증] 원본 변동%와 재계산 변동% 차이 > 0.05%p: {(diff > 0.05).sum()}행")
    df["Return"] = df["Close"].pct_change()          # 일간 수익률 (소수)

    print(f"[결과] {len(df):,}행, 기간 {df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d}")
    return df


# ─────────────────────────────────────────────
# 2. 다각도 분석 (결과는 print로 출력 → GUI에서 문자열로 캡처)
# ─────────────────────────────────────────────
def section(title: str):
    print("\n" + "=" * 60 + f"\n {title}\n" + "=" * 60)


def analyze(df: pd.DataFrame):
    section("① 기술 통계")
    print(df[["Open", "High", "Low", "Close", "ChangePct"]].describe())

    section("② 연도별 요약 (연말 종가, 연간 수익률, 변동성, 최대/최소)")
    yearly = df["Close"].resample("YE").agg(["first", "last", "max", "min"])
    yearly["연간수익률%"] = df["Close"].resample("YE").last().pct_change() * 100
    # 첫 해는 직전 연말 값이 없으므로 그 해 첫 종가 기준으로 계산
    yearly.iloc[0, yearly.columns.get_loc("연간수익률%")] = \
        (yearly["last"].iloc[0] / yearly["first"].iloc[0] - 1) * 100
    yearly["연환산변동성%"] = df["Return"].resample("YE").std() * np.sqrt(252) * 100
    yearly.index = yearly.index.year
    yearly.index.name = "연도"
    yearly.columns = ["연초종가", "연말종가", "최고", "최저", "연간수익률%", "연환산변동성%"]
    print(yearly)
    print(f"\n상승한 해: {(yearly['연간수익률%'] > 0).sum()}년 / 하락한 해: {(yearly['연간수익률%'] <= 0).sum()}년")

    section("③ 전체 기간 성과")
    years = (df.index[-1] - df.index[0]).days / 365.25
    total = df["Close"].iloc[-1] / df["Close"].iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1
    vol = df["Return"].std() * np.sqrt(252)
    print(f"시작 종가 {df['Close'].iloc[0]:,.2f} → 마지막 종가 {df['Close'].iloc[-1]:,.2f}")
    print(f"누적 수익률 {total*100:.2f}% | CAGR {cagr*100:.2f}% | 연환산 변동성 {vol*100:.2f}%")
    print(f"사상 최고 종가 {df['Close'].max():,.2f} ({df['Close'].idxmax():%Y-%m-%d})")
    print(f"최저 종가     {df['Close'].min():,.2f} ({df['Close'].idxmin():%Y-%m-%d})")

    section("④ 최대 낙폭 (Drawdown)")
    peak = df["Close"].cummax()
    dd = df["Close"] / peak - 1
    trough = dd.idxmin()
    peak_date = df["Close"][:trough].idxmax()
    recovered = df.index[(df.index > trough) & (df["Close"] >= df["Close"][peak_date])]
    print(f"MDD {dd.min()*100:.2f}%  고점 {peak_date:%Y-%m-%d} → 저점 {trough:%Y-%m-%d}")
    print("전고점 회복일:", f"{recovered[0]:%Y-%m-%d}" if len(recovered) else "미회복")
    yearly_mdd = df["Close"].groupby(df.index.year).apply(lambda s: (s / s.cummax() - 1).min() * 100)
    print("\n연도별 최대 낙폭(%) 하위 5개:")
    print(yearly_mdd.nsmallest(5).to_string())

    section("⑤ 일간 등락 극단값")
    print("최대 상승일 TOP 5:")
    print(df["ChangePct"].nlargest(5).to_string())
    print("\n최대 하락일 TOP 5:")
    print(df["ChangePct"].nsmallest(5).to_string())
    up = (df["Return"] > 0).mean() * 100
    print(f"\n상승일 비율 {up:.1f}% | 하루 ±2% 이상 변동일 {(df['ChangePct'].abs() >= 2).sum()}일")

    section("⑥ 월별 / 요일별 계절성 (평균 수익률 %)")
    monthly_ret = df["Close"].resample("ME").last().pct_change() * 100
    by_month = monthly_ret.groupby(monthly_ret.index.month).agg(["mean", "median", lambda s: (s > 0).mean() * 100])
    by_month.columns = ["평균%", "중앙값%", "상승확률%"]
    print(by_month)
    weekday = ["월", "화", "수", "목", "금"]
    by_wd = (df["Return"] * 100).groupby(df.index.dayofweek).agg(["mean", "std", "count"])
    by_wd.index = [weekday[i] for i in by_wd.index]
    by_wd.columns = ["평균%", "표준편차%", "일수"]
    print("\n", by_wd)

    section("⑦ 이동평균 추세 (마지막 거래일 기준)")
    for w in (20, 60, 120, 200):
        df[f"MA{w}"] = df["Close"].rolling(w).mean()
    last = df.iloc[-1]
    for w in (20, 60, 120, 200):
        print(f"MA{w:<3}: {last[f'MA{w}']:,.2f}  (종가 대비 {(last['Close']/last[f'MA{w}']-1)*100:+.2f}%)")
    cross = np.sign(df["MA60"] - df["MA200"]).diff()
    print(f"골든크로스(MA60↑MA200) {int((cross > 0).sum())}회, 데드크로스 {int((cross < 0).sum())}회")

    return yearly, dd


# ─────────────────────────────────────────────
# 3. 시각화 (GUI 캔버스의 Figure에 그림)
# ─────────────────────────────────────────────
def plot_close_line(fig: Figure, df: pd.DataFrame, start: str, end: str):
    """종가 기준 라인그래프 (기본 2000년 1월 ~ 2019년 12월)"""
    fig.clear()
    ax = fig.add_subplot()
    s = df.loc[start:end, "Close"]
    if s.empty:
        ax.text(0.5, 0.5, "선택한 기간에 데이터가 없습니다.", ha="center", va="center",
                transform=ax.transAxes, fontsize=14)
        return
    # 이동평균은 전체 데이터로 계산한 뒤 잘라야 기간 앞부분도 값이 나온다
    ma200 = df["Close"].rolling(200).mean().loc[start:end]
    ax.plot(s.index, s.values, color="#1f77b4", linewidth=1.2, label="종가")
    ax.plot(ma200.index, ma200.values, color="#ff7f0e", linewidth=1, alpha=0.8, label="200일 이동평균")

    # 최고점이 기간 앞쪽이면 라벨을 오른쪽에, 뒤쪽이면 왼쪽에 두어 축 밖으로 잘리지 않게 한다
    left_half = s.idxmax() < s.index[0] + (s.index[-1] - s.index[0]) / 2
    ax.annotate(f"최고 {s.max():,.0f}\n({s.idxmax():%Y-%m-%d})", xy=(s.idxmax(), s.max()),
                xytext=(30 if left_half else -110, -25), textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color="gray"), fontsize=9)
    ax.annotate(f"최저 {s.min():,.0f}\n({s.idxmin():%Y-%m-%d})", xy=(s.idxmin(), s.min()),
                xytext=(20, 30), textcoords="offset points",
                arrowprops=dict(arrowstyle="->", color="gray"), fontsize=9)

    ax.set_title(f"S&P 500 종가 추이 ({s.index.min():%Y.%m} ~ {s.index.max():%Y.%m})",
                 fontsize=15, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("종가 (포인트)")
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=24))
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()


def plot_dashboard(fig: Figure, df: pd.DataFrame, yearly: pd.DataFrame, dd: pd.Series):
    """다각도 분석 보조 차트 4종"""
    fig.clear()
    axes = fig.subplots(2, 2)

    ax = axes[0, 0]
    colors = ["#2ca02c" if v > 0 else "#d62728" for v in yearly["연간수익률%"]]
    ax.bar(yearly.index, yearly["연간수익률%"], color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(yearly.index)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title("연간 수익률 (%)")
    ax.grid(axis="y", alpha=0.3)

    ax = axes[0, 1]
    ax.fill_between(dd.index, dd * 100, 0, color="#d62728", alpha=0.4)
    ax.set_title("고점 대비 낙폭 (Drawdown, %)")
    ax.grid(alpha=0.3)

    ax = axes[1, 0]
    ax.hist(df["ChangePct"].dropna(), bins=100, color="#1f77b4", alpha=0.8)
    ax.set_title("일간 변동률 분포 (%)")
    ax.set_xlim(-8, 8)
    ax.grid(alpha=0.3)

    ax = axes[1, 1]
    rolling_vol = df["Return"].rolling(60).std() * np.sqrt(252) * 100
    ax.plot(rolling_vol.index, rolling_vol, color="#9467bd", linewidth=1)
    ax.set_title("60일 롤링 연환산 변동성 (%)")
    ax.grid(alpha=0.3)

    fig.suptitle("S&P 500 다각도 분석", fontsize=16, fontweight="bold")
    fig.tight_layout()


# ─────────────────────────────────────────────
# 4. GUI
# ─────────────────────────────────────────────
class DataFrameModel(QAbstractTableModel):
    """DataFrame을 QTableView에 보여 주는 읽기 전용 모델"""

    def __init__(self, df: pd.DataFrame, index_label: str):
        super().__init__()
        self.df = df
        self.headers = [index_label] + [str(c) for c in df.columns]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        value = self.df.index[row] if col == 0 else self.df.iat[row, col - 1]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, pd.Timestamp):
                return f"{value:%Y-%m-%d}"
            if isinstance(value, (float, np.floating)):
                return "" if np.isnan(value) else f"{value:,.2f}"
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and col > 0:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and isinstance(value, (float, np.floating)):
            name = self.headers[col]
            if name in ("ChangePct", "Return", "연간수익률%") and value < 0:
                return Qt.GlobalColor.blue
            if name in ("ChangePct", "Return", "연간수익률%") and value > 0:
                return Qt.GlobalColor.red
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None


class ChartTab(QWidget):
    """Matplotlib Figure + 확대/이동/저장 툴바"""

    def __init__(self, figsize):
        super().__init__()
        self.figure = Figure(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout = QVBoxLayout(self)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)


class MainWindow(QMainWindow):
    def __init__(self, path: str | None):
        super().__init__()
        self.setWindowTitle("S&P 500 과거 데이터 분석")
        self.resize(1300, 850)
        self.df: pd.DataFrame | None = None

        # 상단: 파일 / 기간 / 버튼
        self.open_btn = QPushButton("CSV 열기")
        self.path_label = QLabel("파일을 선택하세요.")
        self.path_label.setStyleSheet("color: gray;")
        self.start_edit = QDateEdit(QDate(2000, 1, 1))
        self.end_edit = QDateEdit(QDate(2019, 12, 31))
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
        self.plot_btn = QPushButton("그래프 갱신")
        self.save_csv_btn = QPushButton("정제 데이터 저장")
        self.save_png_btn = QPushButton("그래프 PNG 저장")

        top = QHBoxLayout()
        top.addWidget(self.open_btn)
        top.addWidget(self.path_label, 1)
        top.addWidget(QLabel("기간"))
        top.addWidget(self.start_edit)
        top.addWidget(QLabel("~"))
        top.addWidget(self.end_edit)
        top.addWidget(self.plot_btn)
        top.addWidget(self.save_csv_btn)
        top.addWidget(self.save_png_btn)

        # 탭: 종가 그래프 / 분석 차트 / 분석 리포트 / 연도별 요약 / 정제 데이터 / 클렌징 로그
        mono = QFont("Consolas", 10)
        self.close_tab = ChartTab((14, 6))
        self.dash_tab = ChartTab((15, 10))
        self.report_text = QTextEdit(readOnly=True)
        self.report_text.setFont(mono)
        self.yearly_view = QTableView()
        self.data_view = QTableView()
        self.clean_text = QTextEdit(readOnly=True)
        self.clean_text.setFont(mono)
        for view in (self.yearly_view, self.data_view):
            view.setAlternatingRowColors(True)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.close_tab, "종가 그래프")
        self.tabs.addTab(self.dash_tab, "분석 차트")
        self.tabs.addTab(self.report_text, "분석 리포트")
        self.tabs.addTab(self.yearly_view, "연도별 요약")
        self.tabs.addTab(self.data_view, "정제 데이터")
        self.tabs.addTab(self.clean_text, "클렌징 로그")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.open_btn.clicked.connect(self.choose_file)
        self.plot_btn.clicked.connect(self.draw_close_chart)
        self.save_csv_btn.clicked.connect(self.save_cleaned)
        self.save_png_btn.clicked.connect(self.save_png)
        self.set_loaded(False)

        if path and Path(path).exists():
            self.load(path)

    def set_loaded(self, loaded: bool):
        for w in (self.plot_btn, self.save_csv_btn, self.save_png_btn,
                  self.start_edit, self.end_edit):
            w.setEnabled(loaded)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "S&P 500 CSV 선택", "", "CSV 파일 (*.csv)")
        if path:
            self.load(path)

    def load(self, path: str):
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                df = load_and_clean(path)
            clean_log = buf.getvalue()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                yearly, dd = analyze(df)
            report = buf.getvalue()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"데이터를 처리하지 못했습니다.\n\n{e}")
            return

        self.df = df
        self.path_label.setText(path)
        self.path_label.setStyleSheet("")
        self.clean_text.setPlainText(clean_log)
        self.report_text.setPlainText(report.lstrip("\n"))
        self.yearly_view.setModel(DataFrameModel(yearly, "연도"))
        self.data_view.setModel(DataFrameModel(df, "Date"))

        # 데이터 범위 밖으로 기간을 고르지 못하게 제한
        lo, hi = df.index.min(), df.index.max()
        for edit in (self.start_edit, self.end_edit):
            edit.setDateRange(QDate(lo.year, lo.month, lo.day), QDate(hi.year, hi.month, hi.day))

        plot_dashboard(self.dash_tab.figure, df, yearly, dd)
        self.dash_tab.canvas.draw()
        self.draw_close_chart()
        self.set_loaded(True)
        self.statusBar().showMessage(
            f"{len(df):,}행 로드 완료 · 데이터 기간 {lo:%Y-%m-%d} ~ {hi:%Y-%m-%d}")

    def draw_close_chart(self):
        if self.df is None:
            return
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        if start > end:
            QMessageBox.warning(self, "기간 오류", "시작일이 종료일보다 늦습니다.")
            return
        plot_close_line(self.close_tab.figure, self.df, start, end)
        self.close_tab.canvas.draw()
        self.tabs.setCurrentWidget(self.close_tab)

    def save_cleaned(self):
        path, _ = QFileDialog.getSaveFileName(self, "정제 데이터 저장", "sp500_cleaned.csv",
                                              "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, encoding="utf-8-sig")
            self.statusBar().showMessage(f"저장 완료: {path}")

    def save_png(self):
        # 현재 보고 있는 탭이 분석 차트면 그것을, 아니면 종가 그래프를 저장
        tab = self.dash_tab if self.tabs.currentWidget() is self.dash_tab else self.close_tab
        default = "sp500_analysis_dashboard.png" if tab is self.dash_tab else "sp500_close.png"
        path, _ = QFileDialog.getSaveFileName(self, "그래프 저장", default, "PNG 이미지 (*.png)")
        if path:
            tab.figure.savefig(path, dpi=150)
            self.statusBar().showMessage(f"저장 완료: {path}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
