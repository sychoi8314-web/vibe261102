"""
네이버 뉴스 크롤러 GUI 앱 (PyQt6 + requests + BeautifulSoup4)

1) 네이버 검색 결과 페이지에서 기사 목록(제목, 언론사, 날짜, 요약, 링크)을 수집하고
2) '네이버뉴스' 링크가 있는 기사는 기사 본문까지 가져와 화면에 표시하고 CSV로 저장합니다.

설치: pip install PyQt6 requests beautifulsoup4 openpyxl
실행: python naver_news_crawler.py
"""

import csv
import re
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

# 사용자가 제공한 통합검색 URL (기사 블록은 보통 3건만 노출됨)
SEARCH_URL = (
    "https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0"
    "&ie=utf8&query=%EB%B0%98%EB%8F%84%EC%B2%B4&ackey=cgdps5ha"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 네이버는 클래스명이 난독화(랜덤 문자열)되어 자주 바뀌므로,
# 비교적 안정적인 data-heatmap-target 속성을 기준으로 요소를 찾는다.
TITLE_SEL = 'a[data-heatmap-target=".tit"]'
BODY_SEL = 'a[data-heatmap-target=".body"]'
PRESS_SEL = 'a[data-heatmap-target=".prof"]'
NAVER_NEWS_SEL = 'a[data-heatmap-target=".nav"]'

DATE_RE = re.compile(r"^(\d+(초|분|시간|일|주|개월) 전|\d{4}\.\d{1,2}\.\d{1,2}\.?)$")

TABS = {"통합검색 (기사 3건 내외)": "nexearch", "뉴스 탭 (기사 10건 이상)": "news"}


# ----------------------------------------------------------------------
# 크롤링 로직
# ----------------------------------------------------------------------
def get_soup(url: str) -> BeautifulSoup:
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def clean(text: str) -> str:
    """'새 창 열림' 같은 스크린리더용 문구와 중복 공백 제거"""
    text = text.replace("새 창 열림", "")
    return re.sub(r"\s+", " ", text).strip()


def build_url(query: str, tab: str) -> str:
    # 기본 검색어 + 통합검색이면 사용자가 제공한 URL을 그대로 사용
    if query == "반도체" and tab == "nexearch":
        return SEARCH_URL
    return f"https://search.naver.com/search.naver?where={tab}&query={quote(query)}"


def find_item_container(title_a):
    """제목 링크에서 위로 올라가며 기사 1건을 감싸는 컨테이너를 찾는다.
    (부모로 한 단계 더 올라가면 제목이 2개 이상 포함되는 지점)"""
    node = title_a
    while node.parent is not None:
        if len(node.parent.select(TITLE_SEL)) > 1:
            return node
        node = node.parent
    return node


def parse_search_results(soup: BeautifulSoup) -> list[dict]:
    articles = []
    seen = set()

    for title_a in soup.select(TITLE_SEL):
        link = title_a.get("href", "")
        if not link or link in seen:
            continue
        seen.add(link)

        item = find_item_container(title_a)

        summary_a = item.select_one(BODY_SEL)
        naver_a = item.select_one(NAVER_NEWS_SEL)

        # 언론사: .prof 링크 중 텍스트가 있는 것
        press = ""
        for a in item.select(PRESS_SEL):
            if clean(a.get_text()):
                press = clean(a.get_text())
                break

        # 날짜: '31분 전', '2026.11.03.' 형태의 텍스트
        date = ""
        for span in item.find_all("span"):
            t = clean(span.get_text())
            if DATE_RE.match(t):
                date = t
                break

        articles.append(
            {
                "title": clean(title_a.get_text()),
                "press": press,
                "date": date,
                "summary": clean(summary_a.get_text()) if summary_a else "",
                "link": link,
                "naver_link": naver_a.get("href", "") if naver_a else "",
                "content": "",
            }
        )
    return articles


def fetch_naver_article_body(url: str) -> str:
    """네이버뉴스(n.news.naver.com) 기사 본문 추출"""
    soup = get_soup(url)
    body = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    if body is None:
        return ""
    # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
    for tag in body.select("script, style, .img_desc, .end_photo_org em"):
        tag.decompose()
    return clean(body.get_text(" "))


def save_csv(articles: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=list(articles[0].keys()))
        writer.writeheader()
        writer.writerows(articles)


# 엑셀 저장 시 사용할 열 (키, 머리글, 열 너비)
EXCEL_COLUMNS = [
    ("title", "제목", 50),
    ("press", "언론사", 14),
    ("date", "날짜", 12),
    ("summary", "요약", 60),
    ("content", "본문", 80),
    ("link", "원문 링크", 40),
    ("naver_link", "네이버뉴스 링크", 40),
]


def save_excel(articles: list[dict], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    # 머리글
    ws.append([header for _, header, _ in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="03C75A")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 데이터 (엑셀이 허용하지 않는 제어문자 제거, 셀 최대 글자 수 32,767자 제한)
    for art in articles:
        ws.append(
            [ILLEGAL_CHARACTERS_RE.sub("", art.get(key, ""))[:32767] for key, _, _ in EXCEL_COLUMNS]
        )

    wrap = Alignment(wrap_text=True, vertical="top")
    for col, (key, _, width) in enumerate(EXCEL_COLUMNS, 1):
        letter = ws.cell(row=1, column=col).column_letter
        ws.column_dimensions[letter].width = width
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=col)
            cell.alignment = wrap
            # 링크 열은 클릭 가능한 하이퍼링크로
            if key.endswith("link") and cell.value:
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"

    ws.freeze_panes = "A2"  # 머리글 고정
    ws.auto_filter.ref = ws.dimensions  # 필터 추가
    wb.save(path)


# ----------------------------------------------------------------------
# 백그라운드 작업 (GUI가 멈추지 않도록 별도 스레드에서 크롤링)
# ----------------------------------------------------------------------
class CrawlWorker(QThread):
    progress = pyqtSignal(int, int, str)  # 현재, 전체, 메시지
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, url: str, fetch_body: bool):
        super().__init__()
        self.url = url
        self.fetch_body = fetch_body

    def run(self):
        try:
            self.progress.emit(0, 0, "검색 페이지 요청 중...")
            articles = parse_search_results(get_soup(self.url))

            if self.fetch_body:
                total = len(articles)
                for i, art in enumerate(articles, 1):
                    self.progress.emit(i, total, f"본문 수집 중 ({i}/{total})")
                    if art["naver_link"]:
                        try:
                            art["content"] = fetch_naver_article_body(art["naver_link"])
                        except requests.RequestException:
                            pass
                        time.sleep(0.5)  # 서버 부하 방지

            self.finished_ok.emit(articles)
        except Exception as e:
            self.failed.emit(str(e))


# ----------------------------------------------------------------------
# 메인 윈도우
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    COLUMNS = ["제목", "언론사", "날짜", "본문"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1100, 700)
        self.articles: list[dict] = []
        self.worker: CrawlWorker | None = None

        # --- 검색 조건 영역 ---
        self.query_edit = QLineEdit("반도체")
        self.query_edit.setPlaceholderText("검색어 입력")
        self.query_edit.returnPressed.connect(self.start_crawl)

        self.tab_combo = QComboBox()
        self.tab_combo.addItems(TABS.keys())

        self.body_check = QCheckBox("기사 본문 수집")
        self.body_check.setChecked(True)

        self.search_btn = QPushButton("크롤링 시작")
        self.search_btn.clicked.connect(self.start_crawl)

        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_results)

        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel_results)

        top = QHBoxLayout()
        top.addWidget(QLabel("검색어:"))
        top.addWidget(self.query_edit, 1)
        top.addWidget(self.tab_combo)
        top.addWidget(self.body_check)
        top.addWidget(self.search_btn)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # --- 기사 목록 테이블 ---
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(self.COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.open_article)

        # --- 기사 상세 영역 ---
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.setPlaceholderText("목록에서 기사를 선택하면 내용이 표시됩니다. (더블클릭: 브라우저로 열기)")

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setSizes([350, 350])

        # --- 상태 표시줄 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage("검색어를 입력하고 '크롤링 시작'을 누르세요.")

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # --- 크롤링 ---
    def start_crawl(self):
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "알림", "검색어를 입력하세요.")
            return

        url = build_url(query, TABS[self.tab_combo.currentText()])
        self.set_busy(True)
        self.table.setRowCount(0)
        self.detail.clear()

        self.worker = CrawlWorker(url, self.body_check.isChecked())
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, current: int, total: int, message: str):
        # total == 0 이면 진행률을 알 수 없는 상태(움직이는 막대)로 표시
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(message)

    def on_finished(self, articles: list):
        self.articles = articles
        self.table.setRowCount(len(articles))
        for row, art in enumerate(articles):
            values = [art["title"], art["press"], art["date"], "O" if art["content"] else "-"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

        self.set_busy(False)
        self.save_btn.setEnabled(bool(articles))
        self.excel_btn.setEnabled(bool(articles))
        self.statusBar().showMessage(f"기사 {len(articles)}건 수집 완료")
        if articles:
            self.table.selectRow(0)

    def on_failed(self, message: str):
        self.set_busy(False)
        self.statusBar().showMessage("크롤링 실패")
        QMessageBox.critical(self, "오류", f"크롤링 중 오류가 발생했습니다.\n{message}")

    def set_busy(self, busy: bool):
        self.search_btn.setEnabled(not busy)
        self.query_edit.setEnabled(not busy)
        self.tab_combo.setEnabled(not busy)
        self.body_check.setEnabled(not busy)
        if busy:
            self.save_btn.setEnabled(False)
            self.excel_btn.setEnabled(False)
        self.progress_bar.setVisible(busy)

    # --- 상세 보기 / 링크 열기 ---
    def show_detail(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        art = self.articles[rows[0].row()]

        def esc(text: str) -> str:
            return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        html = f"<h2>{esc(art['title'])}</h2>"
        html += f"<p style='color:gray'>{esc(art['press'])} · {esc(art['date'])}</p>"
        html += f"<p><a href='{art['link']}'>원문 보기</a>"
        if art["naver_link"]:
            html += f" &nbsp;|&nbsp; <a href='{art['naver_link']}'>네이버뉴스 보기</a>"
        html += "</p>"
        html += f"<h3>요약</h3><p>{esc(art['summary']) or '(없음)'}</p>"
        if art["content"]:
            html += f"<h3>본문</h3><p style='line-height:160%'>{esc(art['content'])}</p>"
        self.detail.setHtml(html)

    def open_article(self, row: int, _col: int):
        QDesktopServices.openUrl(QUrl(self.articles[row]["link"]))

    # --- 저장 ---
    def save_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV로 저장", "naver_news.csv", "CSV 파일 (*.csv)"
        )
        if not path:
            return
        try:
            save_csv(self.articles, path)
            self.statusBar().showMessage(f"'{path}' 파일로 저장했습니다.")
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def save_excel_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", "naver_news.xlsx", "엑셀 파일 (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            save_excel(self.articles, path)
            self.statusBar().showMessage(f"'{path}' 파일로 저장했습니다.")
        except OSError as e:
            # 같은 파일이 엑셀에서 열려 있으면 PermissionError 발생
            QMessageBox.critical(self, "오류", f"저장 실패 (파일이 열려 있는지 확인하세요): {e}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
