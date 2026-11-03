"""
코스피200 종목 정보 크롤러 GUI 앱 (PyQt6 + requests + BeautifulSoup4)

https://stock.naver.com/market/stock/kr/stocklist/priceTop 페이지는 Next.js로 만들어져
종목 목록을 브라우저에서 JavaScript로 그립니다. 그래서 HTML을 받아 BeautifulSoup로
파싱해도 종목 데이터가 들어 있지 않습니다. 이 앱은 페이지가 내부적으로 호출하는
JSON API에서 데이터를 받습니다. BeautifulSoup는 페이지 HTML에 종목 데이터가 직접
들어 있는지 확인하는 용도로만 씁니다.

1) 코스피200 구성종목 코드 목록을 가져오고 (지수 구성종목 API, 페이지 처리)
2) priceTop 페이지의 종목 목록 API에서 코스피 전 종목을 페이지 단위로 받아
3) 코스피200 종목만 골라 표로 보여 주고 CSV/엑셀로 저장합니다.

설치: pip install PyQt6 requests beautifulsoup4 openpyxl
실행: python kospi200_crawler.py
"""

import csv
import sys
import time

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import QThread, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

PAGE_URL = "https://stock.naver.com/market/stock/kr/stocklist/priceTop"
LIST_API = "https://stock.naver.com/api/domestic/market/stock/default"
KPI200_API = "https://m.stock.naver.com/api/index/KPI200/enrollStocks"
STOCK_URL = "https://stock.naver.com/domestic/stock/{}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": PAGE_URL,
}

# API 필드 → 저장용 컬럼명 (priceTop 목록 API의 응답 필드)
COLUMNS = {
    "itemcode": "종목코드",
    "itemname": "종목명",
    "nowPrice": "현재가",
    "prevChangePrice": "전일대비",
    "prevChangeRate": "등락률(%)",
    "openPrice": "시가",
    "highPrice": "고가",
    "lowPrice": "저가",
    "tradeVolume": "거래량",
    "tradeAmount": "거래대금(원)",
    "marketSum": "시가총액(원)",
    "listedStockCnt": "상장주식수",
    "frgnHoldRate": "외국인비율(%)",
    "per": "PER",
    "eps": "EPS",
    "pbr": "PBR",
    "roe": "ROE(%)",
    "dividend": "주당배당금",
    "dividendRate": "배당수익률(%)",
    "week52HighPrice": "52주최고",
    "week52LowPrice": "52주최저",
    "sales": "매출액(억)",
    "operatingProfit": "영업이익(억)",
    "netIncome": "당기순이익(억)",
    "listedDate": "상장일",
}


# ----------------------------------------------------------------------
# 크롤링 함수
# ----------------------------------------------------------------------
def check_page_html() -> bool:
    """페이지 HTML을 BeautifulSoup로 파싱해 종목 데이터가 들어 있는지 확인합니다."""
    res = requests.get(PAGE_URL, headers=HEADERS, timeout=10)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    return "SK하이닉스" in soup.get_text()


def fetch_kospi200_codes(page_size: int = 20, on_page=None) -> dict[str, int]:
    """코스피200 구성종목 코드를 페이지를 넘겨 가며 전부 가져옵니다.

    API는 pageSize가 너무 크면 400 에러를 내므로 작은 단위로 끊어 받습니다.
    반환값: {종목코드: 지수 내 순위(시가총액 순)}
    """
    codes = {}
    page = 1
    while True:
        res = requests.get(
            KPI200_API,
            headers=HEADERS,
            params={"page": page, "pageSize": page_size},
            timeout=10,
        )
        res.raise_for_status()
        rows = res.json()
        for r in rows:
            codes.setdefault(r["itemCode"], len(codes) + 1)
        if on_page:
            on_page(page, len(codes))
        if len(rows) < page_size:
            break
        page += 1
        time.sleep(0.3)  # 서버 부담을 줄이기 위한 간격
    return codes


def fetch_price_top(page_size: int = 100, on_page=None) -> list[dict]:
    """priceTop 페이지의 코스피 종목 목록을 페이지를 넘겨 가며 끝까지 가져옵니다.

    startIdx는 행 위치가 아니라 0부터 시작하는 페이지 번호입니다.
    (startIdx=1, pageSize=100 → 101~200위)
    """
    stocks = []
    page = 0
    while True:
        params = {
            "tradeType": "KRX",
            "marketType": "KOSPI",
            "orderType": "priceTop",
            "startIdx": page,
            "pageSize": page_size,
        }
        res = requests.get(LIST_API, headers=HEADERS, params=params, timeout=10)
        res.raise_for_status()
        rows = res.json()
        stocks.extend(rows)
        if on_page:
            on_page(page + 1, len(stocks))
        if len(rows) < page_size:
            break
        page += 1
        time.sleep(0.3)
    return stocks


def extract_kospi200(all_stocks: list[dict], kpi200: dict[str, int]) -> list[dict]:
    """priceTop 목록(거래대금 순)에서 코스피200 종목만 골라 저장용 행으로 바꿉니다."""
    rows = []
    seen = set()
    for s in all_stocks:
        code = s["itemcode"]
        # 장중 순위 변동으로 페이지 경계에서 같은 종목이 두 번 나올 수 있어 중복 제거
        if code not in kpi200 or code in seen:
            continue
        seen.add(code)
        row = {"거래대금순위": len(rows) + 1, "지수내순위": kpi200[code]}
        row.update({name: s.get(key) or "" for key, name in COLUMNS.items()})
        rows.append(row)
    return rows


def to_number(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def save_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def save_excel(rows: list[dict], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "코스피200"

    headers = list(rows[0].keys())
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="03C75A")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 숫자 컬럼은 엑셀에서 계산/정렬할 수 있도록 숫자로 저장 (종목코드, 상장일은 문자 유지)
    text_columns = {"종목코드", "종목명", "상장일"}
    for row in rows:
        values = []
        for key in headers:
            value = row[key]
            number = None if key in text_columns else to_number(value)
            values.append(number if number is not None else value)
        ws.append(values)

    for col, key in enumerate(headers, 1):
        letter = ws.cell(row=1, column=col).column_letter
        ws.column_dimensions[letter].width = max(10, len(key) * 2 + 2)
        if key not in text_columns:
            for r in range(2, ws.max_row + 1):
                ws.cell(row=r, column=col).number_format = "#,##0.##"

    ws.freeze_panes = "D2"  # 머리글과 순위/종목코드 고정
    ws.auto_filter.ref = ws.dimensions  # 필터 추가
    wb.save(path)


# ----------------------------------------------------------------------
# 백그라운드 작업 (GUI가 멈추지 않도록 별도 스레드에서 크롤링)
# ----------------------------------------------------------------------
class CrawlWorker(QThread):
    progress = pyqtSignal(int, int, str)  # 현재, 전체, 메시지
    # list로 선언하면 dict가 QVariantMap으로 바뀌며 키가 가나다순으로 정렬되므로 object로 전달
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit(0, 0, "페이지 HTML 확인 중...")
            check_page_html()

            self.progress.emit(0, 0, "코스피200 구성종목 코드 수집 중...")
            kpi200 = fetch_kospi200_codes(
                on_page=lambda page, total: self.progress.emit(
                    0, 0, f"코스피200 구성종목 {page}페이지 (누적 {total}개)"
                )
            )

            # 코스피 상장 종목은 약 950개 → 100개씩 10페이지 정도
            all_stocks = fetch_price_top(
                on_page=lambda page, total: self.progress.emit(
                    min(page, 10), 10, f"priceTop 목록 {page}페이지 (누적 {total}개)"
                )
            )

            self.finished_ok.emit(extract_kospi200(all_stocks, kpi200))
        except Exception as e:
            self.failed.emit(str(e))


# ----------------------------------------------------------------------
# 숫자 기준으로 정렬되는 표 셀
# ----------------------------------------------------------------------
class NumericItem(QTableWidgetItem):
    def __init__(self, text: str, number: float | None):
        super().__init__(text)
        self.number = number
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            # 값이 없는 셀(PER 없음 등)은 가장 작은 값으로 취급
            a = self.number if self.number is not None else float("-inf")
            b = other.number if other.number is not None else float("-inf")
            return a < b
        return super().__lt__(other)


# ----------------------------------------------------------------------
# 메인 윈도우
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    # (표 머리글, 행의 키, 표시 단위로 나눌 값)
    TABLE_COLUMNS = [
        ("거래대금순위", "거래대금순위", 1),
        ("지수내순위", "지수내순위", 1),
        ("종목명", "종목명", None),
        ("종목코드", "종목코드", None),
        ("현재가", "현재가", 1),
        ("전일대비", "전일대비", 1),
        ("등락률(%)", "등락률(%)", 1),
        ("거래량", "거래량", 1),
        ("거래대금(억)", "거래대금(원)", 1e8),
        ("시가총액(억)", "시가총액(원)", 1e8),
        ("PER", "PER", 1),
        ("PBR", "PBR", 1),
        ("외국인(%)", "외국인비율(%)", 1),
    ]
    UP_COLOR = QColor("#E22926")  # 상승: 빨강
    DOWN_COLOR = QColor("#2175F3")  # 하락: 파랑

    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 종목 크롤러")
        self.resize(1200, 750)
        self.rows: list[dict] = []
        self.worker: CrawlWorker | None = None

        # --- 상단 버튼 영역 ---
        self.crawl_btn = QPushButton("크롤링 시작")
        self.crawl_btn.clicked.connect(self.start_crawl)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("종목명 또는 종목코드로 검색")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self.apply_filter)

        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_results)

        self.excel_btn = QPushButton("엑셀 저장")
        self.excel_btn.setEnabled(False)
        self.excel_btn.clicked.connect(self.save_excel_results)

        top = QHBoxLayout()
        top.addWidget(self.crawl_btn)
        top.addWidget(QLabel("검색:"))
        top.addWidget(self.filter_edit, 1)
        top.addWidget(self.save_btn)
        top.addWidget(self.excel_btn)

        # --- 종목 목록 테이블 ---
        headers = [h for h, _, _ in self.TABLE_COLUMNS]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(self.open_stock)

        # --- 종목 상세 영역 ---
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(True)
        self.detail.setPlaceholderText(
            "목록에서 종목을 선택하면 상세 정보가 표시됩니다. (더블클릭: 브라우저로 열기)"
        )

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail)
        splitter.setSizes([850, 350])

        # --- 상태 표시줄 ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.statusBar().addPermanentWidget(self.progress_bar)
        self.statusBar().showMessage("'크롤링 시작'을 누르면 코스피200 종목 정보를 수집합니다.")

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    # --- 크롤링 ---
    def start_crawl(self):
        self.set_busy(True)
        self.table.setRowCount(0)
        self.detail.clear()

        self.worker = CrawlWorker()
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_progress(self, current: int, total: int, message: str):
        # total == 0 이면 진행률을 알 수 없는 상태(움직이는 막대)로 표시
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(message)

    def on_finished(self, rows: list):
        self.rows = rows
        self.fill_table()
        self.set_busy(False)
        self.save_btn.setEnabled(bool(rows))
        self.excel_btn.setEnabled(bool(rows))
        self.statusBar().showMessage(
            f"코스피200 종목 {len(rows)}개 수집 완료 ({time.strftime('%Y-%m-%d %H:%M:%S')})"
        )
        self.apply_filter(self.filter_edit.text())
        if rows:
            self.table.selectRow(0)

    def on_failed(self, message: str):
        self.set_busy(False)
        self.statusBar().showMessage("크롤링 실패")
        QMessageBox.critical(self, "오류", f"크롤링 중 오류가 발생했습니다.\n{message}")

    def set_busy(self, busy: bool):
        self.crawl_btn.setEnabled(not busy)
        if busy:
            self.save_btn.setEnabled(False)
            self.excel_btn.setEnabled(False)
        self.progress_bar.setVisible(busy)

    def fill_table(self):
        self.table.setSortingEnabled(False)  # 채우는 동안 정렬하면 행이 섞임
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            change = to_number(row["등락률(%)"]) or 0
            color = self.UP_COLOR if change > 0 else self.DOWN_COLOR if change < 0 else None
            for c, (_, key, unit) in enumerate(self.TABLE_COLUMNS):
                value = row[key]
                if unit is None:
                    item = QTableWidgetItem(str(value))
                else:
                    number = to_number(value)
                    if number is None:
                        text = "-"
                    else:
                        number /= unit
                        decimals = 2 if key in ("등락률(%)", "PER", "PBR", "외국인비율(%)") else 0
                        text = f"{number:,.{decimals}f}"
                    item = NumericItem(text, number)
                    if color and key in ("현재가", "전일대비", "등락률(%)"):
                        item.setForeground(color)
                # 정렬 후에도 원본 행을 찾을 수 있도록 인덱스 저장
                item.setData(Qt.ItemDataRole.UserRole, r)
                self.table.setItem(r, c, item)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def apply_filter(self, text: str):
        text = text.strip().lower()
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 2).text().lower()
            code = self.table.item(r, 3).text()
            self.table.setRowHidden(r, bool(text) and text not in name and text not in code)

    def selected_row(self) -> dict | None:
        items = self.table.selectedItems()
        if not items:
            return None
        return self.rows[items[0].data(Qt.ItemDataRole.UserRole)]

    # --- 상세 보기 / 링크 열기 ---
    def show_detail(self):
        row = self.selected_row()
        if not row:
            return
        change = to_number(row["등락률(%)"]) or 0
        color = "#E22926" if change > 0 else "#2175F3" if change < 0 else "gray"
        price = to_number(row["현재가"]) or 0
        diff = to_number(row["전일대비"]) or 0

        html = f"<h2>{row['종목명']} <span style='color:gray;font-size:small'>{row['종목코드']}</span></h2>"
        html += (
            f"<p style='font-size:x-large;color:{color}'><b>{price:,.0f}</b> "
            f"<span style='font-size:medium'>{diff:+,.0f} ({change:+.2f}%)</span></p>"
        )
        html += f"<p><a href='{STOCK_URL.format(row['종목코드'])}'>네이버 증권에서 보기</a></p>"
        html += "<table cellspacing='0' cellpadding='3' width='100%'>"
        for key, value in row.items():
            if key in ("종목명", "종목코드"):
                continue
            number = to_number(value) if key != "상장일" else None
            text = f"{number:,.2f}".rstrip("0").rstrip(".") if number is not None else (value or "-")
            html += f"<tr><td style='color:gray'>{key}</td><td align='right'>{text}</td></tr>"
        html += "</table>"
        self.detail.setHtml(html)

    def open_stock(self, _row: int, _col: int):
        row = self.selected_row()
        if row:
            QDesktopServices.openUrl(QUrl(STOCK_URL.format(row["종목코드"])))

    # --- 저장 ---
    def default_name(self, ext: str) -> str:
        return f"kospi200_{time.strftime('%Y%m%d_%H%M')}.{ext}"

    def save_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV로 저장", self.default_name("csv"), "CSV 파일 (*.csv)"
        )
        if not path:
            return
        try:
            save_csv(self.rows, path)
            self.statusBar().showMessage(f"'{path}' 파일로 저장했습니다.")
        except OSError as e:
            QMessageBox.critical(self, "오류", f"저장 실패 (파일이 열려 있는지 확인하세요): {e}")

    def save_excel_results(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "엑셀로 저장", self.default_name("xlsx"), "엑셀 파일 (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            save_excel(self.rows, path)
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
