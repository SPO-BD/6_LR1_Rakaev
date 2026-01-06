import os
import sys

import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit, QFileDialog
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from db_manager import SQLiteManager
from logger import ActionLogger
from plot_utils import get_numeric_df, build_corr_matrix, draw_heatmap, draw_line


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt + SQLite: Визуализация данных")
        self.resize(1100, 700)

        # Пути проекта
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(self.project_root, "db", "app.db")
        self.sqlite = SQLiteManager(self.db_path)

        self.df_cache = {}  # table_name -> DataFrame
        self.logger = ActionLogger()

        # Tabs container
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()
        self.tab5 = QWidget()

        self.tabs.addTab(self.tab1, "1) Статистика / Загрузка")
        self.tabs.addTab(self.tab2, "2) Корреляции (pairplot)")
        self.tabs.addTab(self.tab3, "3) Тепловая карта")
        self.tabs.addTab(self.tab4, "4) Линейный график")
        self.tabs.addTab(self.tab5, "5) Лог действий")

        # Build UI for each tab
        self._build_tab1()
        self._build_tab2()
        self._build_tab3()
        self._build_tab4()
        self._build_tab5()

        # Signals
        self.load_btn.clicked.connect(self.on_load_csv)
        self.table_select.currentIndexChanged.connect(self.on_change_table)
        self.column_select.currentIndexChanged.connect(self.on_change_column)

        # Init: load existing tables from db (если есть)
        self.refresh_tables()

    # ---------- TAB 1 ----------
    def _build_tab1(self):
        layout = QVBoxLayout()

        row = QHBoxLayout()
        self.load_btn = QPushButton("Загрузить CSV в SQLite")
        row.addWidget(self.load_btn)

        row.addWidget(QLabel("Таблица:"))
        self.table_select = QComboBox()
        row.addWidget(self.table_select)

        layout.addLayout(row)

        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)

        self.tab1.setLayout(layout)

    def refresh_tables(self):
        tables = self.sqlite.list_tables()
        self.table_select.blockSignals(True)
        self.table_select.clear()
        self.table_select.addItems(tables)
        self.table_select.blockSignals(False)

        if tables:
            self.table_select.setCurrentIndex(0)
            self.load_table_to_cache(tables[0])
            self.render_all(tables[0])
            self.logger.log(f"Найдены таблицы в БД: {tables}")
        else:
            self.stats_text.setText("В базе данных пока нет таблиц. Нажмите 'Загрузить CSV в SQLite'.")
            self.logger.log("База данных пуста (таблиц нет).")

    def on_load_csv(self):
        self.logger.log("Нажата кнопка загрузки CSV.")

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите CSV файл", self.project_root,
            "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            self.logger.log("Загрузка CSV отменена пользователем.")
            return

        base = os.path.basename(file_path)
        table_name = os.path.splitext(base)[0].replace(" ", "_").replace("-", "_")

        try:
            df = self.sqlite.import_csv_to_table(file_path, table_name)
            self.df_cache[table_name] = df
            self.logger.log(f"CSV '{base}' импортирован в таблицу '{table_name}'.")
        except Exception as e:
            self.logger.log(f"Ошибка импорта CSV: {e}")
            return

        self.refresh_tables()
        idx = self.table_select.findText(table_name)
        if idx >= 0:
            self.table_select.setCurrentIndex(idx)

    def load_table_to_cache(self, table_name: str):
        if table_name in self.df_cache:
            return
        df = self.sqlite.read_table(table_name)
        self.df_cache[table_name] = df

    def on_change_table(self):
        table_name = self.table_select.currentText()
        if not table_name:
            return
        self.logger.log(f"Выбрана таблица: {table_name}")
        self.load_table_to_cache(table_name)
        self.render_all(table_name)

    def render_stats(self, table_name: str):
        df = self.df_cache[table_name]
        rows, cols = df.shape
        txt = []
        txt.append(f"Таблица: {table_name}")
        txt.append(f"Размер: {rows} строк × {cols} столбцов")
        txt.append("")
        txt.append("Столбцы:")
        for c in df.columns:
            txt.append(f" - {c} ({df[c].dtype})")
        txt.append("")
        num = get_numeric_df(df)
        if num.shape[1] > 0:
            txt.append("describe() по числовым столбцам:")
            txt.append(str(num.describe()))
        else:
            txt.append("Числовых столбцов нет.")
        self.stats_text.setText("\n".join(txt))

    # ---------- TAB 2 ----------
    def _build_tab2(self):
        layout = QVBoxLayout()
        self.fig_pair = plt.Figure(figsize=(8, 6))
        self.canvas_pair = FigureCanvas(self.fig_pair)
        layout.addWidget(self.canvas_pair)
        self.tab2.setLayout(layout)

    def render_pairplot(self, table_name: str):
        df = self.df_cache[table_name]
        num = get_numeric_df(df)
        self.fig_pair.clear()
        ax = self.fig_pair.add_subplot(111)

        if num.shape[1] < 2:
            ax.set_title("Недостаточно числовых столбцов для pairplot")
            self.canvas_pair.draw()
            return

        # Упрощение: рисуем корреляционную матрицу как таблицу/картинку на этой вкладке,
        # а полноценный pairplot на больших данных может быть тяжелым.
        corr = num.corr()
        sns.heatmap(corr, ax=ax, annot=True, fmt=".2f")
        ax.set_title("Корреляции (упрощенный вывод вместо тяжелого pairplot)")
        self.canvas_pair.draw()

    # ---------- TAB 3 ----------
    def _build_tab3(self):
        layout = QVBoxLayout()
        self.fig_heat = plt.Figure(figsize=(8, 6))
        self.canvas_heat = FigureCanvas(self.fig_heat)
        layout.addWidget(self.canvas_heat)
        self.tab3.setLayout(layout)

    def render_heatmap(self, table_name: str):
        df = self.df_cache[table_name]
        corr = build_corr_matrix(df)
        self.fig_heat.clear()
        ax = self.fig_heat.add_subplot(111)
        draw_heatmap(ax, corr, title=f"Тепловая карта корреляций: {table_name}")
        self.canvas_heat.draw()

    # ---------- TAB 4 ----------
    def _build_tab4(self):
        layout = QVBoxLayout()

        top = QHBoxLayout()
        top.addWidget(QLabel("Числовой столбец:"))
        self.column_select = QComboBox()
        top.addWidget(self.column_select)
        layout.addLayout(top)

        self.fig_line = plt.Figure(figsize=(8, 6))
        self.canvas_line = FigureCanvas(self.fig_line)
        layout.addWidget(self.canvas_line)

        self.tab4.setLayout(layout)

    def render_columns(self, table_name: str):
        df = self.df_cache[table_name]
        num_cols = list(get_numeric_df(df).columns)

        self.column_select.blockSignals(True)
        self.column_select.clear()
        self.column_select.addItems(num_cols)
        self.column_select.blockSignals(False)

        if num_cols:
            self.column_select.setCurrentIndex(0)
            self.render_line(table_name, num_cols[0])
        else:
            self.fig_line.clear()
            ax = self.fig_line.add_subplot(111)
            ax.set_title("Нет числовых столбцов для линейного графика")
            self.canvas_line.draw()

    def on_change_column(self):
        table_name = self.table_select.currentText()
        col = self.column_select.currentText()
        if not table_name or not col:
            return
        self.logger.log(f"Выбран столбец для линии: {col}")
        self.render_line(table_name, col)

    def render_line(self, table_name: str, col: str):
        df = self.df_cache[table_name]
        self.fig_line.clear()
        ax = self.fig_line.add_subplot(111)
        draw_line(ax, df, col)
        self.canvas_line.draw()
        self.logger.log(f"Построен линейный график по столбцу '{col}'")

    # ---------- TAB 5 ----------
    def _build_tab5(self):
        layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        self.tab5.setLayout(layout)

        self.logger.bind_widget(self.log_text)

    # ---------- render all ----------
    def render_all(self, table_name: str):
        self.render_stats(table_name)
        self.render_pairplot(table_name)
        self.render_heatmap(table_name)
        self.render_columns(table_name)


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
