"""
대한민국 출생아수 분석기 (PyQt6 GUI)

- KOSIS 출생아수·합계출산율 엑셀 파일을 불러와 클렌징 → 다각도 분석 → 라인 그래프
- 클렌징/분석은 birth_analysis.py, 그래프는 birth_line_chart.py 를 재사용
사용법: python birth_analysis_gui.py [엑셀파일경로]
"""

import contextlib
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from birth_analysis import DEFAULT_XLSX, analyze, load_and_clean, save_excel
from birth_line_chart import plot_births_line

# 음수일 때 파란색, 양수일 때 빨간색으로 보여 줄 컬럼
NEGATIVE, POSITIVE = QColor("#2a78d6"), QColor("#d03b3b")
SIGNED_COLUMNS = {"출생아수_증감", "출생아수_증감률(%)", "자연증가건수", "자연증가율", "CAGR(%)"}


class DataFrameModel(QAbstractTableModel):
    """DataFrame을 QTableView에 보여 주는 읽기 전용 모델"""

    def __init__(self, df: pd.DataFrame, show_index: bool):
        super().__init__()
        self.df = df
        self.show_index = show_index
        self.headers = ([str(df.index.name or "")] if show_index else []) + [str(c) for c in df.columns]

    def rowCount(self, parent=None):
        return len(self.df)

    def columnCount(self, parent=None):
        return len(self.headers)

    def _value(self, row: int, col: int):
        if self.show_index:
            return self.df.index[row] if col == 0 else self.df.iat[row, col - 1]
        return self.df.iat[row, col]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        value = self._value(index.row(), index.column())
        is_num = isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)
        if role == Qt.ItemDataRole.DisplayRole:
            if value is pd.NA or (isinstance(value, float) and np.isnan(value)):
                return ""
            if isinstance(value, (float, np.floating)):
                return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.3f}".rstrip("0").rstrip(".")
            if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
                name = self.headers[index.column()]
                return str(value) if "연도" in name else f"{value:,}"
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and is_num:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ForegroundRole and is_num and value is not pd.NA:
            if self.headers[index.column()] in SIGNED_COLUMNS:
                if value < 0:
                    return NEGATIVE
                if value > 0:
                    return POSITIVE
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section]
        return None


def make_table_view() -> QTableView:
    view = QTableView()
    view.setAlternatingRowColors(True)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    return view


class MainWindow(QMainWindow):
    def __init__(self, path: str | None):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 분석기")
        self.resize(1300, 850)
        self.df: pd.DataFrame | None = None
        self.results: dict[str, pd.DataFrame] = {}

        # 상단: 파일 / 기간 / 버튼
        self.open_btn = QPushButton("엑셀 열기")
        self.path_label = QLabel("파일을 선택하세요.")
        self.path_label.setStyleSheet("color: gray;")
        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(1970, 2025)
        self.start_spin.setValue(1970)
        self.end_spin.setValue(2025)
        self.plot_btn = QPushButton("그래프 갱신")
        self.save_csv_btn = QPushButton("정제 데이터 CSV")
        self.save_xlsx_btn = QPushButton("분석 결과 엑셀")
        self.save_png_btn = QPushButton("그래프 PNG")

        top = QHBoxLayout()
        top.addWidget(self.open_btn)
        top.addWidget(self.path_label, 1)
        top.addWidget(QLabel("기간"))
        top.addWidget(self.start_spin)
        top.addWidget(QLabel("~"))
        top.addWidget(self.end_spin)
        top.addWidget(self.plot_btn)
        top.addWidget(self.save_csv_btn)
        top.addWidget(self.save_xlsx_btn)
        top.addWidget(self.save_png_btn)

        # 탭 1: 출생아수 그래프
        self.figure = Figure(figsize=(12, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        chart_tab = QWidget()
        chart_layout = QVBoxLayout(chart_tab)
        chart_layout.addWidget(NavigationToolbar2QT(self.canvas, chart_tab))
        chart_layout.addWidget(self.canvas)

        # 탭 2: 분석 리포트 / 탭 5: 클렌징 로그 (콘솔 출력 그대로)
        mono = QFont("Consolas", 10)
        self.report_text = QTextEdit(readOnly=True)
        self.clean_text = QTextEdit(readOnly=True)
        for text in (self.report_text, self.clean_text):
            text.setFont(mono)

        # 탭 3: 분석표 (콤보박스로 표 선택)
        self.table_combo = QComboBox()
        self.result_view = make_table_view()
        table_tab = QWidget()
        table_layout = QVBoxLayout(table_tab)
        combo_row = QHBoxLayout()
        combo_row.addWidget(QLabel("분석표"))
        combo_row.addWidget(self.table_combo, 1)
        table_layout.addLayout(combo_row)
        table_layout.addWidget(self.result_view)

        # 탭 4: 정제 데이터
        self.data_view = make_table_view()

        self.tabs = QTabWidget()
        self.tabs.addTab(chart_tab, "출생아수 그래프")
        self.tabs.addTab(self.report_text, "분석 리포트")
        self.tabs.addTab(table_tab, "분석표")
        self.tabs.addTab(self.data_view, "정제 데이터")
        self.tabs.addTab(self.clean_text, "클렌징 로그")

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.open_btn.clicked.connect(self.choose_file)
        self.plot_btn.clicked.connect(self.draw_chart)
        self.table_combo.currentTextChanged.connect(self.show_result_table)
        self.save_csv_btn.clicked.connect(self.save_csv)
        self.save_xlsx_btn.clicked.connect(self.save_xlsx)
        self.save_png_btn.clicked.connect(self.save_png)
        self.set_loaded(False)

        if path and Path(path).exists():
            self.load(path)

    def set_loaded(self, loaded: bool):
        for w in (self.plot_btn, self.save_csv_btn, self.save_xlsx_btn, self.save_png_btn,
                  self.start_spin, self.end_spin, self.table_combo):
            w.setEnabled(loaded)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "출생아수 엑셀 선택", "", "엑셀 파일 (*.xlsx)")
        if path:
            self.load(path)

    def load(self, path: str):
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                df = load_and_clean(Path(path))
            clean_log = buf.getvalue()

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                results = analyze(df)
            report = buf.getvalue()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 실패", f"데이터를 처리하지 못했습니다.\n\n{e}")
            return

        self.df, self.results = df, results
        self.path_label.setText(path)
        self.path_label.setStyleSheet("")
        self.clean_text.setPlainText(clean_log.lstrip("\n"))
        self.report_text.setPlainText(report.lstrip("\n"))
        self.data_view.setModel(DataFrameModel(df, show_index=False))

        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        self.table_combo.addItems(results.keys())
        self.table_combo.blockSignals(False)
        self.show_result_table(self.table_combo.currentText())

        lo, hi = int(df["연도"].min()), int(df["연도"].max())
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(lo, hi)
        self.start_spin.setValue(max(lo, 1970))
        self.end_spin.setValue(min(hi, 2025))

        self.set_loaded(True)
        self.draw_chart()
        self.statusBar().showMessage(f"{len(df)}개 연도 로드 완료 · 데이터 기간 {lo}~{hi}")

    def show_result_table(self, name: str):
        table = self.results.get(name)
        if table is None:
            return
        # 행 이름이 의미 있는 표(기술통계·연대별평균·상관계수)만 인덱스를 보여 준다
        show_index = not pd.api.types.is_integer_dtype(table.index)
        if show_index and table.index.name is None:
            table = table.rename_axis("지표")
        self.result_view.setModel(DataFrameModel(table, show_index=show_index))

    def draw_chart(self):
        if self.df is None:
            return
        start, end = self.start_spin.value(), self.end_spin.value()
        if start >= end:
            QMessageBox.warning(self, "기간 오류", "시작 연도는 종료 연도보다 앞서야 합니다.")
            return
        plot_births_line(self.figure, self.df, start, end)
        self.canvas.draw()
        self.tabs.setCurrentIndex(0)

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "정제 데이터 저장", "births_clean.csv",
                                              "CSV 파일 (*.csv)")
        if path:
            self.df.to_csv(path, index=False, encoding="utf-8-sig")
            self.statusBar().showMessage(f"저장 완료: {path}")

    def save_xlsx(self):
        path, _ = QFileDialog.getSaveFileName(self, "분석 결과 저장", "births_analysis.xlsx",
                                              "엑셀 파일 (*.xlsx)")
        if path:
            save_excel(self.df, self.results, Path(path))
            self.statusBar().showMessage(f"저장 완료: {path}")

    def save_png(self):
        default = f"births_line_{self.start_spin.value()}_{self.end_spin.value()}.png"
        path, _ = QFileDialog.getSaveFileName(self, "그래프 저장", default, "PNG 이미지 (*.png)")
        if path:
            self.figure.savefig(path, dpi=150, facecolor=self.figure.get_facecolor())
            self.statusBar().showMessage(f"저장 완료: {path}")


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Malgun Gothic", 10))
    window = MainWindow(sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_XLSX))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
