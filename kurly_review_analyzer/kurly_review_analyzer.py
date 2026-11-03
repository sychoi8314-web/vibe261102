"""
마켓컬리 상품 후기 감성 분석 GUI 앱 (PyQt6 + requests + Pandas + Matplotlib)

1) 상품 페이지가 후기 목록을 그릴 때 호출하는 공개 JSON API를 그대로 호출해
   후기를 약 300개 수집하고 (페이지마다 잠깐 쉬면서, 커서 방식으로 넘김)
2) 한국어 감성 사전(키워드 + 부정어 처리)으로 긍정/부정/중립을 분류한 뒤
3) 긍·부정 비율 파이차트와 감성별 상위 키워드를 앱 안에 보여 줍니다.

※ 컬리 후기 API에는 별점 필드가 없어 키워드 점수만으로 분류합니다.

설치: pip install PyQt6 requests pandas matplotlib openpyxl
실행: python kurly_review_analyzer.py [상품 URL]
"""

import re
import sys
import time
from collections import Counter

import matplotlib
import pandas as pd
import requests
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

DEFAULT_URL = "https://www.kurly.com/goods/1000572062?collectionCode=2611-blackweek-home-01"
REVIEW_API = "https://api.kurly.com/product-review/v4/contents-products/{no}/reviews"
PAGE_SIZE = 10          # 상품 페이지가 후기 목록에 쓰는 크기와 동일
PAGE_DELAY = 0.5        # 페이지 사이 대기(초) - 서버에 부담을 주지 않도록
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.kurly.com/",
    "Origin": "https://www.kurly.com",
}

# 감성별 색상 (긍정=파랑, 부정=빨강, 중립=회색)
COLORS = {"긍정": "#2a78d6", "부정": "#e34948", "중립": "#a8a7a2"}

matplotlib.rcParams["font.family"] = "Malgun Gothic"   # 한글 폰트 (Windows)
matplotlib.rcParams["axes.unicode_minus"] = False


# ─────────────────────────────────────────────
# 1. 후기 수집
# ─────────────────────────────────────────────
def parse_product_no(url: str) -> str:
    """https://www.kurly.com/goods/1000572062?... → '1000572062'"""
    m = re.search(r"/goods/(\d+)", url) or re.fullmatch(r"\s*(\d+)\s*", url)
    if not m:
        raise ValueError("URL에서 상품 번호(/goods/숫자)를 찾지 못했습니다.")
    return m.group(1)


def fetch_reviews(product_no: str, target: int, on_progress=None) -> pd.DataFrame:
    """최신순으로 target개가 모일 때까지 nextCursor(after)를 따라 페이지를 넘긴다."""
    session = requests.Session()
    session.headers.update(HEADERS)
    rows, after = [], None
    while len(rows) < target:
        params = {"sortType": "RECENTLY", "size": PAGE_SIZE, "onlyImage": "false"}
        if after:
            params["after"] = after
        resp = session.get(REVIEW_API.format(no=product_no), params=params, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("success"):
            raise RuntimeError(body.get("message") or "후기 API가 실패 응답을 보냈습니다.")
        data = body["data"]
        for r in data["reviews"]:
            rows.append({
                "후기번호": r["no"],
                "작성일": r["registeredAt"],
                "작성자": r["ownerName"],
                "상품명": r["dealProductName"],
                "내용": (r["contents"] or "").strip(),
                "좋아요": r["likeCount"],
                "사진수": len(r.get("images") or []),
            })
        if on_progress:
            on_progress(min(len(rows), target), target)
        after = (data.get("nextCursor") or {}).get("after")
        if not data["reviews"] or not after:      # 더 이상 후기가 없음
            break
        time.sleep(PAGE_DELAY)

    df = pd.DataFrame(rows[:target])
    if df.empty:
        return df
    df = df.drop_duplicates(subset="후기번호")
    df["작성일"] = pd.to_datetime(df["작성일"], errors="coerce")
    return df


# ─────────────────────────────────────────────
# 2. 감성 분석 (한국어 키워드 사전 + 부정어 처리)
# ─────────────────────────────────────────────
# 부정 표현이 긍정처럼 보이는 경우("안 짜요") → 먼저 찾아서 긍정으로 세고 문장에서 지운다
POS_OVERRIDE = [
    r"(안|덜)\s?짜", r"짜지\s?않", r"안\s?느끼", r"느끼하지\s?않", r"안\s?질기", r"질기지\s?않",
    r"안\s?비리", r"비리지\s?않", r"냄새(도|가)?\s?(안|없)", r"잡내(도|가)?\s?(안|없)",
    r"안\s?달", r"달지\s?않", r"쎄지\s?않", r"냄새\s?(나지\s?않|안\s?나)",
    r"실패\s?(는|가)?\W?\s?(없|안)", r"후회\s?(는|가)?\W?\s?(없|안)", r"아쉬운\s?(점|게)\s?없",
    r"단점(이|은)?\s?없", r"흠\s?잡을",
]
# 긍정어를 뒤집는 부정 표현 → 부정으로 세고 지운다
NEG_OVERRIDE = [
    r"맛있지\s?(않|는\s?않)", r"맛있진\s?않", r"안\s?맛있", r"좋지\s?(않|는\s?않)", r"좋진\s?않", r"안\s?좋",
    r"추천\s?(안|하지\s?않|은\s?안|못)", r"재구매\s?(는|은)?\s?(안|없|않|못|글쎄|고민)",
    r"다시\s?(는|안)\s?(안\s?)?(사|구매|시키)", r"만족\s?(스럽지\s?)?(못|않)", r"별로",
    r"그닥", r"그다지", r"그저\s?그", r"(으면|면)\s?(더\s?)?좋겠",
]
POS_WORDS = [
    "맛있", "맛나", "맛난", "존맛", "꿀맛", "맛집", "좋아", "좋음", "좋네", "좋습", "좋은", "좋고", "좋았",
    "최고", "만족", "추천", "강추", "재구매", "또 구매", "또 살", "또 시킬", "또 주문", "자주",
    "부드럽", "부들부들", "연하", "든든", "간편", "편하", "편리", "굿", "훌륭", "짱", "대박",
    "넉넉", "푸짐", "신선", "깔끔", "괜찮", "필수", "쟁여", "믿고", "믿먹", "사랑", "행복",
    "감사", "인생", "잘 먹", "잘먹", "맛있게", "칭찬", "감동", "적당", "가성비", "저렴", "애정",
    "단골", "최애", "완벽", "고소", "감칠맛", "풍부", "알차", "실하", "쟁임", "쟁겨", "쟁이",
    "맛은 있", "맛 있", "맛잇", "마싯", "무난", "먹을만", "뚝딱", "으뜸", "시원", "애용", "선호",
    "보증수표", "구비",
]
NEG_WORDS = [
    "맛없", "아쉽", "아쉬", "실망", "별로", "비싸", "비쌉", "질기", "질겨", "느끼", "비리", "비린",
    "잡내", "누린내", "짜요", "짜다", "짜네", "짜서", "짰", "짜고", "짜게", "너무 달", "달아요",
    "싱거", "밍밍", "적어요", "적네", "적다", "부족", "작아요", "작네", "양이 적", "후회", "최악",
    "불량", "상했", "녹아", "터져", "파손", "찢어", "이상한 맛", "냄새", "불만", "환불", "교환",
    "애매", "비추", "글쎄", "그냥 그", "기대 이하", "기대이하", "속았", "실패", "퍽퍽", "딱딱",
    "기름이 많", "지방이 많", "비계", "흐물", "불어", "질겼", "작은 양", "번거", "힘드", "헷갈",
]


def _count_terms(text: str, terms) -> list[str]:
    return [t for t in terms if t in text]


def score_review(text: str) -> tuple[int, list[str], list[str]]:
    """(점수, 긍정 근거, 부정 근거). 점수 = 긍정 매칭 수 - 부정 매칭 수"""
    t = re.sub(r"\s+", " ", text)
    pos_hits, neg_hits = [], []
    for pat in POS_OVERRIDE:
        for m in re.finditer(pat, t):
            pos_hits.append(m.group(0))
        t = re.sub(pat, " ", t)
    for pat in NEG_OVERRIDE:
        for m in re.finditer(pat, t):
            neg_hits.append(m.group(0))
        t = re.sub(pat, " ", t)
    pos_hits += _count_terms(t, POS_WORDS)
    neg_hits += _count_terms(t, NEG_WORDS)

    # "~지만/~는데" 뒤의 내용이 결론인 경우가 많아 뒤쪽 절에 가중치 1을 더 준다
    tail = re.split(r"(지만|는데|은데|긴 한데|으나)", t)[-1] if re.search(r"(지만|는데|은데|으나)", t) else ""
    bonus = len(_count_terms(tail, POS_WORDS)) - len(_count_terms(tail, NEG_WORDS)) if tail else 0
    score = len(pos_hits) - len(neg_hits) + (1 if bonus > 0 else -1 if bonus < 0 else 0)
    return score, pos_hits, neg_hits


def classify(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    results = df["내용"].apply(score_review)
    df["점수"] = results.str[0]
    df["긍정근거"] = results.str[1].apply(", ".join)
    df["부정근거"] = results.str[2].apply(", ".join)
    df["감성"] = pd.cut(df["점수"], bins=[-float("inf"), -1, 0, float("inf")],
                       labels=["부정", "중립", "긍정"]).astype(str)
    return df


# 키워드 추출: 2글자 이상 한글 어절에서 흔한 조사/어미를 떼어 내고 불용어 제거
JOSA = re.compile(r"(이에요|예요|에요|어요|아요|해요|했어요|습니다|합니다|니다|네요|구요|고요|"
                  r"이랑|랑|에서|으로|로|에게|까지|부터|은|는|이|가|을|를|도|만|의|에|와|과|요|고|서|게|ㅎ+|ㅋ+)$")
STOPWORDS = {"너무", "정말", "진짜", "그냥", "항상", "아주", "많이", "조금", "같아", "같은", "있어",
             "있는", "없이", "먹었", "먹어", "먹기", "먹을", "먹으", "구매", "구매했", "주문", "제품", "상품",
             "이번", "다음", "그리", "사리원", "불고기", "소불고기", "전골", "컬리", "마켓컬리", "있습",
             "해서", "하고", "하는", "했는", "했습", "해먹", "같습", "좋아", "맛있", "생각", "한번", "그리고",
             "근데", "역시", "완전", "엄청", "되는", "되어", "하게", "합니", "때문", "정도", "좀", "더"}


def extract_keywords(texts: pd.Series, top_n: int = 15) -> pd.Series:
    counter = Counter()
    for text in texts:
        words = set()                 # 한 후기 안에서 같은 단어는 1번만 센다 (언급 후기 수)
        for w in re.findall(r"[가-힣]{2,}", text):
            w = JOSA.sub("", w)
            if len(w) >= 2 and w not in STOPWORDS:
                words.add(w)
        counter.update(words)
    return pd.Series(dict(counter.most_common(top_n)), dtype="int64")


def build_summary(df: pd.DataFrame) -> tuple[str, dict]:
    counts = df["감성"].value_counts().reindex(["긍정", "부정", "중립"], fill_value=0)
    ratio = counts / counts.sum() * 100
    keywords = {s: extract_keywords(df.loc[df["감성"] == s, "내용"]) for s in ("긍정", "부정")}

    lines = [f"수집 후기 {len(df):,}개  ·  기간 {df['작성일'].min():%Y-%m-%d %H:%M} ~ "
             f"{df['작성일'].max():%Y-%m-%d %H:%M}", ""]
    lines.append("■ 감성 분포")
    for s in counts.index:
        lines.append(f"  {s}: {counts[s]:>4}개 ({ratio[s]:5.1f}%)")
    pn = counts["긍정"] + counts["부정"]
    if pn:
        lines.append(f"  (중립 제외 시) 긍정 {counts['긍정'] / pn * 100:.1f}% / 부정 {counts['부정'] / pn * 100:.1f}%")
    lines.append(f"  평균 감성 점수 {df['점수'].mean():+.2f}  ·  평균 글자 수 {df['내용'].str.len().mean():.0f}자")

    for s in ("긍정", "부정"):
        lines += ["", f"■ {s} 후기 상위 키워드 (언급 후기 수)"]
        kw = keywords[s]
        lines.append("  " + ("  ".join(f"{k}({v})" for k, v in kw.items()) if len(kw) else "(없음)"))
        evid = df.loc[df["감성"] == s, "긍정근거" if s == "긍정" else "부정근거"]
        terms = Counter(t for e in evid for t in e.split(", ") if t).most_common(10)
        lines.append("  판정 근거 표현: " + ("  ".join(f"{k}({v})" for k, v in terms) or "(없음)"))

    neg = df[df["감성"] == "부정"].sort_values("점수").head(5)
    if len(neg):
        lines += ["", "■ 대표 부정 후기"]
        lines += [f"  [{r.점수:+d}] {r.내용[:80]}" for r in neg.itertuples()]
    pos = df[df["감성"] == "긍정"].sort_values("점수", ascending=False).head(5)
    if len(pos):
        lines += ["", "■ 대표 긍정 후기"]
        lines += [f"  [{r.점수:+d}] {r.내용[:80]}" for r in pos.itertuples()]
    return "\n".join(lines), keywords


# ─────────────────────────────────────────────
# 3. 시각화
# ─────────────────────────────────────────────
def plot_sentiment(fig: Figure, df: pd.DataFrame, keywords: dict, title: str):
    """왼쪽: 감성 비율 파이차트 / 오른쪽: 긍정·부정 상위 키워드 막대"""
    fig.clear()
    gs = fig.add_gridspec(2, 2, width_ratios=[1.25, 1])
    ax = fig.add_subplot(gs[:, 0])
    counts = df["감성"].value_counts().reindex(["긍정", "부정", "중립"], fill_value=0)
    counts = counts[counts > 0]
    wedges, _, autotexts = ax.pie(
        counts.values, labels=None, colors=[COLORS[s] for s in counts.index],
        autopct=lambda p: f"{p:.1f}%", pctdistance=0.72, startangle=90, counterclock=False,
        wedgeprops=dict(edgecolor="white", linewidth=2, width=0.55),
        textprops=dict(color="white", fontsize=12, fontweight="bold"))
    ax.text(0, 0.06, f"{len(df):,}", ha="center", va="center", fontsize=22, fontweight="bold", color="#222")
    ax.text(0, -0.14, "개 후기", ha="center", va="center", fontsize=11, color="#666")
    ax.legend(wedges, [f"{s}  {n}개" for s, n in counts.items()], loc="lower center",
              bbox_to_anchor=(0.5, -0.08), ncol=len(counts), frameon=False, fontsize=11)
    ax.set_title("감성 분포 (긍정 · 부정 · 중립)", fontsize=13, fontweight="bold")
    ax.set_aspect("equal")

    for row, s in enumerate(("긍정", "부정")):
        kax = fig.add_subplot(gs[row, 1])
        kw = keywords[s].head(8)[::-1]
        if kw.empty:
            kax.text(0.5, 0.5, f"{s} 키워드 없음", ha="center", va="center", transform=kax.transAxes)
            kax.axis("off")
            continue
        kax.barh(kw.index, kw.values, color=COLORS[s], height=0.6)
        for y, v in enumerate(kw.values):
            kax.text(v, y, f" {v}", va="center", fontsize=9, color="#444")
        kax.set_title(f"{s} 후기 상위 키워드", fontsize=11, fontweight="bold", loc="left")
        kax.set_xlabel("언급 후기 수", fontsize=9, color="#666")
        kax.spines[["top", "right"]].set_visible(False)
        kax.grid(axis="x", alpha=0.25)
        kax.set_xlim(0, kw.max() * 1.18)

    fig.suptitle(title, fontsize=15, fontweight="bold")
    fig.tight_layout()


# ─────────────────────────────────────────────
# 4. GUI
# ─────────────────────────────────────────────
class DataFrameModel(QAbstractTableModel):
    """DataFrame을 QTableView에 보여 주는 읽기 전용 모델"""

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.df = df
        self.headers = [str(c) for c in df.columns]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self.df.iat[index.row(), index.column()]
        name = self.headers[index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, pd.Timestamp):
                return f"{value:%Y-%m-%d %H:%M}"
            if name == "점수":
                return f"{value:+d}"
            return str(value)
        if role == Qt.ItemDataRole.ToolTipRole and name == "내용":
            return str(value)
        if role == Qt.ItemDataRole.ForegroundRole and name in ("감성", "점수"):
            sentiment = self.df.iat[index.row(), self.headers.index("감성")]
            return QColor(COLORS[sentiment]) if sentiment != "중립" else QColor("#777")
        if role == Qt.ItemDataRole.TextAlignmentRole and name in ("점수", "감성", "좋아요"):
            return Qt.AlignmentFlag.AlignCenter
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


class CollectWorker(QThread):
    """후기 수집 + 감성 분석을 백그라운드에서 수행 (GUI가 멈추지 않도록)"""
    progress = pyqtSignal(int, int)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, url: str, target: int):
        super().__init__()
        self.url, self.target = url, target

    def run(self):
        try:
            product_no = parse_product_no(self.url)
            df = fetch_reviews(product_no, self.target, self.progress.emit)
            if df.empty:
                raise RuntimeError("수집된 후기가 없습니다.")
            self.finished_ok.emit(classify(df))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class MainWindow(QMainWindow):
    def __init__(self, url: str):
        super().__init__()
        self.setWindowTitle("마켓컬리 후기 감성 분석")
        self.resize(1300, 850)
        self.df: pd.DataFrame | None = None
        self.worker: CollectWorker | None = None

        # 상단: URL / 수집 개수 / 버튼
        self.url_edit = QLineEdit(url)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(10, 2000)
        self.count_spin.setSingleStep(50)
        self.count_spin.setValue(300)
        self.count_spin.setSuffix(" 개")
        self.run_btn = QPushButton("수집 · 분석")
        self.save_csv_btn = QPushButton("CSV 저장")
        self.save_xlsx_btn = QPushButton("엑셀 저장")
        self.save_png_btn = QPushButton("차트 PNG 저장")

        top = QHBoxLayout()
        top.addWidget(QLabel("상품 URL"))
        top.addWidget(self.url_edit, 1)
        top.addWidget(QLabel("수집 개수"))
        top.addWidget(self.count_spin)
        top.addWidget(self.run_btn)
        top.addWidget(self.save_csv_btn)
        top.addWidget(self.save_xlsx_btn)
        top.addWidget(self.save_png_btn)

        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m 개")
        self.progress.setValue(0)

        # 탭: 감성 차트 / 후기 목록 / 키워드 요약
        self.chart_tab = ChartTab((13, 7))
        self.table_view = QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setWordWrap(False)
        self.summary_text = QTextEdit(readOnly=True)
        self.summary_text.setFont(QFont("Malgun Gothic", 10))

        self.tabs = QTabWidget()
        self.tabs.addTab(self.chart_tab, "감성 파이차트")
        self.tabs.addTab(self.table_view, "후기 목록")
        self.tabs.addTab(self.summary_text, "키워드 요약")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.run_btn.clicked.connect(self.start_collect)
        self.save_csv_btn.clicked.connect(self.save_csv)
        self.save_xlsx_btn.clicked.connect(self.save_xlsx)
        self.save_png_btn.clicked.connect(self.save_png)
        self.set_loaded(False)
        self.statusBar().showMessage("URL과 수집 개수를 확인하고 [수집 · 분석]을 누르세요.")

    def set_loaded(self, loaded: bool):
        for w in (self.save_csv_btn, self.save_xlsx_btn, self.save_png_btn):
            w.setEnabled(loaded)

    def start_collect(self):
        self.run_btn.setEnabled(False)
        self.progress.setRange(0, self.count_spin.value())
        self.progress.setValue(0)
        self.statusBar().showMessage("후기 수집 중... (페이지마다 잠시 쉬어 가며 요청합니다)")
        self.worker = CollectWorker(self.url_edit.text().strip(), self.count_spin.value())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, done: int, total: int):
        self.progress.setValue(done)
        self.statusBar().showMessage(f"후기 수집 중... {done} / {total}")

    def on_failed(self, msg: str):
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage("수집 실패")
        QMessageBox.critical(self, "수집 실패", f"후기를 가져오지 못했습니다.\n\n{msg}")

    def on_done(self, df: pd.DataFrame):
        self.run_btn.setEnabled(True)
        self.df = df
        self.progress.setValue(self.progress.maximum() if len(df) >= self.progress.maximum() else len(df))
        summary, keywords = build_summary(df)
        self.summary_text.setPlainText(summary)

        view_cols = ["작성일", "감성", "점수", "내용", "긍정근거", "부정근거", "좋아요", "작성자"]
        self.table_view.setModel(DataFrameModel(df[view_cols].reset_index(drop=True)))
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(view_cols.index("내용"), QHeaderView.ResizeMode.Stretch)

        product = df["상품명"].mode().iat[0] if df["상품명"].notna().any() else "상품"
        plot_sentiment(self.chart_tab.figure, df, keywords, f"{product} 후기 감성 분석")
        self.chart_tab.canvas.draw()
        self.tabs.setCurrentWidget(self.chart_tab)
        self.set_loaded(True)

        counts = df["감성"].value_counts()
        self.statusBar().showMessage(
            f"{len(df):,}개 분석 완료 · 긍정 {counts.get('긍정', 0)} / 부정 {counts.get('부정', 0)} "
            f"/ 중립 {counts.get('중립', 0)}")

    def export_df(self) -> pd.DataFrame:
        return self.df.assign(작성일=self.df["작성일"].dt.strftime("%Y-%m-%d %H:%M:%S"))

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "kurly_reviews.csv", "CSV 파일 (*.csv)")
        if path:
            self.export_df().to_csv(path, index=False, encoding="utf-8-sig")
            self.statusBar().showMessage(f"저장 완료: {path}")

    def save_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "엑셀 저장", "kurly_reviews.xlsx", "엑셀 파일 (*.xlsx)")
        if path:
            try:
                self.export_df().to_excel(path, index=False, sheet_name="후기")
            except Exception as e:
                QMessageBox.critical(self, "저장 실패", f"엑셀 저장에 실패했습니다.\n\n{e}")
                return
            self.statusBar().showMessage(f"저장 완료: {path}")

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "차트 저장", "kurly_sentiment.png", "PNG 이미지 (*.png)")
        if path:
            self.chart_tab.figure.savefig(path, dpi=150)
            self.statusBar().showMessage(f"저장 완료: {path}")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 10))
    window = MainWindow(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
