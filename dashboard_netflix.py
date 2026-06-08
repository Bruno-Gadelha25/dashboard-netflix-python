from __future__ import annotations

import csv
import os
import re
import sqlite3
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import matplotlib
import pandas as pd

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


APP_TITLE = "Dashboard Netflix - Análise de Dados"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "netflix.db"

# Paleta de cores pensada para um dashboard escuro e legível.
APP_BG = "#0f172a"
PANEL_BG = "#111827"
CARD_BG = "#1e293b"
CONTROL_BG = "#334155"
TEXT = "#f8fafc"
MUTED_TEXT = "#cbd5e1"
ACCENT = "#38bdf8"
ACCENT_2 = "#f97316"
SUCCESS = "#22c55e"
WARN = "#eab308"
ERROR = "#ef4444"

FONT_FAMILY = "Segoe UI"

REQUIRED_SOURCE_COLUMNS = {
    "show_id",
    "type",
    "title",
    "director",
    "cast",
    "country",
    "date_added",
    "release_year",
    "rating",
    "duration",
    "listed_in",
    "description",
}

DISPLAY_COLUMNS = [
    "title",
    "type",
    "main_country",
    "release_year",
    "rating",
    "date_added",
    "listed_in",
]


def normalize_column_name(name: str) -> str:
    """Padroniza o nome de uma coluna para snake_case simples."""
    normalized = name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def clean_text_series(series: pd.Series) -> pd.Series:
    """Remove espaços extras e substitui vazios por 'Desconhecido'."""
    cleaned = series.astype("string").str.strip()
    cleaned = cleaned.replace(
        {
            "": "Desconhecido",
            "nan": "Desconhecido",
            "NaN": "Desconhecido",
            "<NA>": "Desconhecido",
            "None": "Desconhecido",
        }
    )
    return cleaned.fillna("Desconhecido")


def display_value(value) -> str:
    """Formata valores para exibição no Treeview e no export."""
    if value is None or pd.isna(value):
        return "Desconhecido"
    if isinstance(value, str):
        value = value.strip()
        return value if value else "Desconhecido"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def read_csv_header(path: Path) -> list[str]:
    """Lê apenas o cabeçalho do CSV usando codificações comuns."""
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                reader = csv.reader(file)
                return next(reader)
        except Exception as exc:  # noqa: BLE001 - queremos tentar outra codificação
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError(f"Não foi possível ler o cabeçalho de {path.name}")


def find_compatible_csv(base_dir: Path) -> Path:
    """
    Localiza o primeiro CSV compatível com o esquema da Netflix.

    A busca prioriza arquivos com nomes que contenham 'netflix' e, em seguida,
    os arquivos cujo cabeçalho mais se aproxima do dataset esperado.
    """
    csv_files = sorted(base_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"Nenhum arquivo CSV foi encontrado em {base_dir}."
        )

    scored: list[tuple[int, int, Path]] = []
    for path in csv_files:
        try:
            header = read_csv_header(path)
        except Exception:
            continue

        normalized_header = {normalize_column_name(column) for column in header}
        matches = len(REQUIRED_SOURCE_COLUMNS & normalized_header)
        name_bonus = 0
        lower_name = path.name.lower()
        if lower_name == "netflix_titles.csv":
            name_bonus += 50
        if "netflix" in lower_name:
            name_bonus += 20

        score = matches * 10 + name_bonus
        scored.append((score, matches, path))

    if not scored:
        return csv_files[0]

    scored.sort(key=lambda item: (-item[0], -item[1], str(item[2]).lower()))
    best_score, best_matches, best_path = scored[0]

    if best_matches < len(REQUIRED_SOURCE_COLUMNS):
        raise ValueError(
            "O CSV encontrado não possui o esquema da Netflix esperado. "
            f"Arquivo mais próximo: {best_path.name}."
        )

    return best_path


def explode_multivalue_column(df: pd.DataFrame, source_column: str, target_column: str) -> pd.DataFrame:
    """Explode colunas separadas por vírgula para tabelas auxiliares."""
    exploded = df[["show_id", source_column]].copy()
    exploded[target_column] = exploded[source_column].fillna("Desconhecido").astype(str).str.split(",")
    exploded = exploded.explode(target_column)
    exploded[target_column] = exploded[target_column].astype(str).str.strip()
    exploded[target_column] = exploded[target_column].replace(
        {
            "": "Desconhecido",
            "nan": "Desconhecido",
            "<NA>": "Desconhecido",
        }
    )
    exploded = exploded[["show_id", target_column]].drop_duplicates()
    return exploded


class NetflixDataset:
    """Responsável por localizar, limpar e persistir os dados no SQLite."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.csv_path = find_compatible_csv(base_dir)
        self.db_path = base_dir / "netflix.db"
        self.raw_df = self._load_csv()
        self.df = self._clean_dataframe(self.raw_df)
        self.generos_df = explode_multivalue_column(self.df, "listed_in", "genero")
        self.paises_df = explode_multivalue_column(self.df, "country", "pais")
        self._write_database()
        self.conn = sqlite3.connect(self.db_path)

    def _load_csv(self) -> pd.DataFrame:
        """Carrega o CSV principal da Netflix."""
        return pd.read_csv(self.csv_path, encoding="utf-8-sig", low_memory=False)

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Padroniza colunas, remove duplicados e cria colunas derivadas."""
        df = df.copy()
        df.columns = [normalize_column_name(column) for column in df.columns]
        df = df.rename(columns={"cast": "cast_members"})

        required_columns = {column for column in REQUIRED_SOURCE_COLUMNS if column != "cast"} | {
            "cast_members"
        }
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(
                "O CSV não possui todas as colunas esperadas para o dashboard Netflix. "
                f"Colunas ausentes: {sorted(missing)}"
            )

        # Remove duplicados com base no identificador do título.
        df = df.drop_duplicates(subset=["show_id"], keep="first").reset_index(drop=True)

        # Limpa as colunas de texto conhecidas.
        text_columns = [
            "show_id",
            "type",
            "title",
            "director",
            "cast_members",
            "country",
            "rating",
            "duration",
            "listed_in",
            "description",
        ]
        for column in text_columns:
            if column in df.columns:
                df[column] = clean_text_series(df[column])

        # Converte colunas numéricas.
        df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce").astype("Int64")

        # Converte date_added para data e cria year_added / month_added.
        date_added = pd.to_datetime(df["date_added"], errors="coerce")
        df["date_added"] = date_added.dt.strftime("%Y-%m-%d").fillna("Desconhecido")
        df["year_added"] = date_added.dt.year.astype("Int64")
        df["month_added"] = date_added.dt.month.astype("Int64")

        # Primeira parte do campo country para facilitar análises.
        df["main_country"] = df["country"].apply(self._extract_main_country)

        ordered_columns = [
            "show_id",
            "type",
            "title",
            "director",
            "cast_members",
            "country",
            "main_country",
            "date_added",
            "year_added",
            "month_added",
            "release_year",
            "rating",
            "duration",
            "listed_in",
            "description",
        ]
        existing_order = [column for column in ordered_columns if column in df.columns]
        remaining_columns = [column for column in df.columns if column not in existing_order]
        return df[existing_order + remaining_columns]

    @staticmethod
    def _extract_main_country(value: str) -> str:
        if value is None:
            return "Desconhecido"
        text = str(value).strip()
        if not text or text == "Desconhecido":
            return "Desconhecido"
        return text.split(",")[0].strip() or "Desconhecido"

    def _write_database(self) -> None:
        """Cria ou recria o banco SQLite com as tabelas solicitadas."""
        with sqlite3.connect(self.db_path) as conn:
            self.df.to_sql("titulos", conn, if_exists="replace", index=False)
            self.generos_df.to_sql("generos", conn, if_exists="replace", index=False)
            self.paises_df.to_sql("paises", conn, if_exists="replace", index=False)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_show_id ON titulos(show_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_type ON titulos(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_release_year ON titulos(release_year)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_rating ON titulos(rating)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_generos_show_id ON generos(show_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_paises_show_id ON paises(show_id)")

    def close(self) -> None:
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    def query_filtered_titles(
        self,
        type_value: str,
        country_value: str,
        year_value: str,
        rating_value: str,
        search_value: str,
    ) -> pd.DataFrame:
        """Consulta os títulos aplicando os filtros informados na interface."""
        search_text = search_value.strip().lower()
        query = """
            SELECT DISTINCT
                t.show_id,
                t.type,
                t.title,
                t.director,
                t.cast_members,
                t.country,
                t.main_country,
                t.date_added,
                t.year_added,
                t.month_added,
                t.release_year,
                t.rating,
                t.duration,
                t.listed_in,
                t.description
            FROM titulos t
            LEFT JOIN paises p ON t.show_id = p.show_id
            WHERE (:type_value = 'Todos' OR t.type = :type_value)
              AND (:country_value = 'Todos' OR p.pais = :country_value)
              AND (
                    :year_value = 'Todos'
                    OR COALESCE(CAST(t.release_year AS TEXT), 'Desconhecido') = :year_value
                  )
              AND (:rating_value = 'Todos' OR COALESCE(t.rating, 'Desconhecido') = :rating_value)
              AND (
                    :search_text = ''
                    OR LOWER(t.title) LIKE :search_like
                  )
            ORDER BY t.title COLLATE NOCASE
        """
        params = {
            "type_value": type_value,
            "country_value": country_value,
            "year_value": year_value,
            "rating_value": rating_value,
            "search_text": search_text,
            "search_like": f"%{search_text}%",
        }
        return pd.read_sql_query(query, self.conn, params=params)


class NetflixDashboardApp:
    """Janela principal do dashboard em Tkinter."""

    def __init__(self, root: tk.Tk, dataset: NetflixDataset) -> None:
        self.root = root
        self.dataset = dataset
        self.filtered_df = dataset.df.copy()

        self.root.title(APP_TITLE)
        self.root.geometry("1600x980")
        self.root.minsize(1360, 860)
        self.root.configure(bg=APP_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._configure_style()
        self._build_ui()
        self._populate_filter_values()
        self.apply_filters()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(
            ".",
            background=APP_BG,
            foreground=TEXT,
            font=(FONT_FAMILY, 10),
        )
        style.configure("TFrame", background=APP_BG)
        style.configure("TLabel", background=APP_BG, foreground=TEXT)
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=CARD_BG,
            foreground=TEXT,
            padding=(16, 8),
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", CONTROL_BG)],
            foreground=[("selected", TEXT)],
        )
        style.configure(
            "TButton",
            background=CONTROL_BG,
            foreground=TEXT,
            padding=(12, 8),
            borderwidth=0,
            focusthickness=2,
            focuscolor=APP_BG,
        )
        style.map(
            "TButton",
            background=[("active", CARD_BG)],
            foreground=[("active", TEXT)],
        )
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground=APP_BG,
            padding=(12, 8),
            borderwidth=0,
            focusthickness=2,
            focuscolor=APP_BG,
            font=(FONT_FAMILY, 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#0ea5e9")],
            foreground=[("active", APP_BG)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=CONTROL_BG,
            background=CONTROL_BG,
            foreground=TEXT,
            arrowcolor=TEXT,
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", CONTROL_BG)],
            foreground=[("readonly", TEXT)],
            background=[("readonly", CONTROL_BG)],
        )
        style.configure(
            "Treeview",
            background=CARD_BG,
            fieldbackground=CARD_BG,
            foreground=TEXT,
            rowheight=28,
            bordercolor=APP_BG,
            lightcolor=APP_BG,
            darkcolor=APP_BG,
        )
        style.map("Treeview", background=[("selected", ACCENT)])
        style.configure(
            "Treeview.Heading",
            background=CONTROL_BG,
            foreground=TEXT,
            font=(FONT_FAMILY, 10, "bold"),
            relief="flat",
        )
        style.map("Treeview.Heading", background=[("active", CONTROL_BG)])

        matplotlib.rcParams.update(
            {
                "figure.facecolor": CARD_BG,
                "axes.facecolor": CARD_BG,
                "axes.edgecolor": MUTED_TEXT,
                "axes.labelcolor": TEXT,
                "axes.titlecolor": TEXT,
                "xtick.color": TEXT,
                "ytick.color": TEXT,
                "text.color": TEXT,
                "grid.color": "#475569",
                "font.size": 10,
                "font.family": FONT_FAMILY,
            }
        )

    def _build_ui(self) -> None:
        main = tk.Frame(self.root, bg=APP_BG)
        main.pack(fill="both", expand=True)

        self._build_header(main)
        self._build_metrics(main)
        self._build_filters(main)
        self._build_content(main)
        self._build_footer(main)

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=APP_BG)
        header.pack(fill="x", padx=18, pady=(16, 8))

        title_row = tk.Frame(header, bg=APP_BG)
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="Dashboard Netflix",
            bg=APP_BG,
            fg=TEXT,
            font=(FONT_FAMILY, 24, "bold"),
        ).pack(anchor="w")

        subtitle_text = (
            "Análise interativa do catálogo, com limpeza de dados, SQLite e gráficos dinâmicos."
        )
        tk.Label(
            header,
            text=subtitle_text,
            bg=APP_BG,
            fg=MUTED_TEXT,
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w", pady=(4, 0))

        self.source_label = tk.Label(
            header,
            text=f"CSV encontrado: {self.dataset.csv_path.name}",
            bg=APP_BG,
            fg=ACCENT,
            font=(FONT_FAMILY, 9, "bold"),
        )
        self.source_label.pack(anchor="w", pady=(4, 0))

    def _build_metrics(self, parent: tk.Widget) -> None:
        metrics = tk.Frame(parent, bg=APP_BG)
        metrics.pack(fill="x", padx=18, pady=(4, 10))
        for index in range(5):
            metrics.columnconfigure(index, weight=1, uniform="metrics")

        metric_specs = [
            ("total_titulos", "Total de títulos"),
            ("total_filmes", "Total de filmes"),
            ("total_series", "Total de séries"),
            ("ano_mais_recente", "Ano mais recente"),
            ("pais_mais_titulos", "País com mais títulos"),
        ]
        self.metric_value_labels: dict[str, tk.Label] = {}

        for index, (key, title) in enumerate(metric_specs):
            card = tk.Frame(metrics, bg=CARD_BG, highlightthickness=1, highlightbackground=CONTROL_BG)
            card.grid(row=0, column=index, sticky="nsew", padx=6)

            tk.Label(
                card,
                text=title,
                bg=CARD_BG,
                fg=MUTED_TEXT,
                font=(FONT_FAMILY, 10),
                anchor="w",
            ).pack(fill="x", padx=14, pady=(12, 4))

            value_label = tk.Label(
                card,
                text="0",
                bg=CARD_BG,
                fg=TEXT,
                font=(FONT_FAMILY, 18, "bold"),
                anchor="w",
            )
            value_label.pack(fill="x", padx=14, pady=(0, 12))
            self.metric_value_labels[key] = value_label

    def _build_filters(self, parent: tk.Widget) -> None:
        filters = tk.Frame(parent, bg=PANEL_BG, highlightthickness=1, highlightbackground=CONTROL_BG)
        filters.pack(fill="x", padx=18, pady=(0, 10))
        for index in range(6):
            filters.columnconfigure(index, weight=1)

        tk.Label(
            filters,
            text="Filtros e busca",
            bg=PANEL_BG,
            fg=TEXT,
            font=(FONT_FAMILY, 12, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6), columnspan=6)

        self.type_var = tk.StringVar(value="Todos")
        self.country_var = tk.StringVar(value="Todos")
        self.year_var = tk.StringVar(value="Todos")
        self.rating_var = tk.StringVar(value="Todos")
        self.search_var = tk.StringVar(value="")

        self.type_combo = self._add_combo(filters, 1, 0, "Tipo", self.type_var)
        self.country_combo = self._add_combo(filters, 1, 1, "País", self.country_var)
        self.year_combo = self._add_combo(filters, 1, 2, "Ano de lançamento", self.year_var)
        self.rating_combo = self._add_combo(filters, 1, 3, "Classificação", self.rating_var)

        search_frame = tk.Frame(filters, bg=PANEL_BG)
        search_frame.grid(row=1, column=4, sticky="nsew", padx=10, pady=(0, 12))
        tk.Label(
            search_frame,
            text="Busca por título",
            bg=PANEL_BG,
            fg=TEXT,
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w")
        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=CARD_BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=CONTROL_BG,
            highlightcolor=ACCENT,
            font=(FONT_FAMILY, 10),
        )
        search_entry.pack(fill="x", pady=(6, 0))
        search_entry.bind("<Return>", lambda _event: self.apply_filters())

        buttons_frame = tk.Frame(filters, bg=PANEL_BG)
        buttons_frame.grid(row=1, column=5, sticky="e", padx=10, pady=(18, 12))

        tk.Button(
            buttons_frame,
            text="Aplicar filtros",
            command=self.apply_filters,
            bg=ACCENT,
            fg=APP_BG,
            activebackground="#0ea5e9",
            activeforeground=APP_BG,
            relief="flat",
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_frame,
            text="Limpar",
            command=self.reset_filters,
            bg=CONTROL_BG,
            fg=TEXT,
            activebackground=CARD_BG,
            activeforeground=TEXT,
            relief="flat",
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            buttons_frame,
            text="Exportar CSV",
            command=self.export_csv_dialog,
            bg=SUCCESS,
            fg=APP_BG,
            activebackground="#16a34a",
            activeforeground=APP_BG,
            relief="flat",
            font=(FONT_FAMILY, 10, "bold"),
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side="left")

    def _add_combo(
        self,
        parent: tk.Widget,
        row: int,
        column: int,
        label_text: str,
        variable: tk.StringVar,
    ) -> ttk.Combobox:
        wrapper = tk.Frame(parent, bg=PANEL_BG)
        wrapper.grid(row=row, column=column, sticky="nsew", padx=10, pady=(0, 12))
        tk.Label(
            wrapper,
            text=label_text,
            bg=PANEL_BG,
            fg=TEXT,
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w")
        combo = ttk.Combobox(
            wrapper,
            textvariable=variable,
            state="readonly",
            values=["Todos"],
            font=(FONT_FAMILY, 10),
        )
        combo.pack(fill="x", pady=(6, 0))
        combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_filters())
        return combo

    def _build_content(self, parent: tk.Widget) -> None:
        content = tk.Frame(parent, bg=APP_BG)
        content.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        content.rowconfigure(0, weight=3)
        content.rowconfigure(1, weight=2)
        content.columnconfigure(0, weight=1)

        self.chart_notebook = ttk.Notebook(content)
        self.chart_notebook.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        self.charts: dict[str, dict[str, object]] = {}
        chart_specs = [
            ("tipo", "Filmes x Séries"),
            ("ano_lancamento", "Títulos por ano de lançamento"),
            ("paises", "Top 10 países com mais títulos"),
            ("generos", "Top 10 gêneros mais comuns"),
            ("classificacao", "Classificação indicativa"),
            ("adicionados", "Títulos adicionados por ano"),
        ]
        for key, tab_text in chart_specs:
            tab = tk.Frame(self.chart_notebook, bg=CARD_BG)
            self.chart_notebook.add(tab, text=tab_text)

            figure = Figure(figsize=(8, 4.2), dpi=100, facecolor=CARD_BG)
            axis = figure.add_subplot(111)
            axis.set_facecolor(CARD_BG)

            canvas = FigureCanvasTkAgg(figure, master=tab)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)

            self.charts[key] = {"figure": figure, "axis": axis, "canvas": canvas}

        table_container = tk.Frame(content, bg=APP_BG, highlightthickness=1, highlightbackground=CONTROL_BG)
        table_container.grid(row=1, column=0, sticky="nsew")
        table_container.rowconfigure(1, weight=1)
        table_container.columnconfigure(0, weight=1)

        tk.Label(
            table_container,
            text="Dados filtrados",
            bg=APP_BG,
            fg=TEXT,
            font=(FONT_FAMILY, 12, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        tree_frame = tk.Frame(table_container, bg=APP_BG)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=DISPLAY_COLUMNS,
            show="headings",
            selectmode="browse",
        )
        for column in DISPLAY_COLUMNS:
            self.tree.heading(column, text=self._format_column_heading(column))
            width = 200
            if column in {"release_year"}:
                width = 120
            elif column in {"rating"}:
                width = 110
            elif column in {"date_added"}:
                width = 130
            elif column in {"main_country"}:
                width = 180
            self.tree.column(column, width=width, anchor="w")

        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

    def _build_footer(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=APP_BG)
        footer.pack(fill="x", padx=18, pady=(0, 14))
        self.status_var = tk.StringVar(value="Pronto para análise.")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=APP_BG,
            fg=MUTED_TEXT,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x")

    @staticmethod
    def _format_column_heading(column: str) -> str:
        return {
            "main_country": "País principal",
            "release_year": "Ano lançamento",
            "date_added": "Data adicionada",
            "listed_in": "Gêneros",
        }.get(column, column.replace("_", " ").title())

    def _populate_filter_values(self) -> None:
        """Preenche as listas de filtros com os valores disponíveis."""
        self.type_combo["values"] = ["Todos"] + self._unique_sorted_values(self.dataset.df["type"])
        self.country_combo["values"] = ["Todos"] + self._unique_sorted_values(self.dataset.df["main_country"])
        years = pd.to_numeric(self.dataset.df["release_year"], errors="coerce").dropna().astype(int)
        self.year_combo["values"] = ["Todos"] + [str(year) for year in sorted(years.unique())]
        self.rating_combo["values"] = ["Todos"] + self._unique_sorted_values(self.dataset.df["rating"])

        self.type_var.set("Todos")
        self.country_var.set("Todos")
        self.year_var.set("Todos")
        self.rating_var.set("Todos")

    @staticmethod
    def _unique_sorted_values(series: pd.Series) -> list[str]:
        values = (
            series.fillna("Desconhecido")
            .astype(str)
            .str.strip()
            .replace({"": "Desconhecido", "nan": "Desconhecido", "<NA>": "Desconhecido"})
            .unique()
        )
        return sorted(values.tolist(), key=str.casefold)

    def reset_filters(self) -> None:
        self.type_var.set("Todos")
        self.country_var.set("Todos")
        self.year_var.set("Todos")
        self.rating_var.set("Todos")
        self.search_var.set("")
        self.apply_filters()

    def apply_filters(self) -> pd.DataFrame:
        self.filtered_df = self.dataset.query_filtered_titles(
            type_value=self.type_var.get(),
            country_value=self.country_var.get(),
            year_value=self.year_var.get(),
            rating_value=self.rating_var.get(),
            search_value=self.search_var.get(),
        )
        self._refresh_metrics()
        self._refresh_charts()
        self._refresh_table()
        self._refresh_status()
        return self.filtered_df

    def _refresh_metrics(self) -> None:
        df = self.filtered_df
        total_titles = int(len(df))
        total_filmes = int((df["type"] == "Movie").sum()) if not df.empty else 0
        total_series = int((df["type"] == "TV Show").sum()) if not df.empty else 0

        release_years = pd.to_numeric(df["release_year"], errors="coerce").dropna()
        ano_mais_recente = str(int(release_years.max())) if not release_years.empty else "Desconhecido"

        paises = (
            df["main_country"]
            .fillna("Desconhecido")
            .astype(str)
            .str.strip()
        )
        paises = paises[paises.ne("Desconhecido") & paises.ne("")]
        pais_mais_titulos = paises.value_counts().idxmax() if not paises.empty else "Desconhecido"

        self.metric_value_labels["total_titulos"].configure(text=str(total_titles))
        self.metric_value_labels["total_filmes"].configure(text=str(total_filmes))
        self.metric_value_labels["total_series"].configure(text=str(total_series))
        self.metric_value_labels["ano_mais_recente"].configure(text=ano_mais_recente)
        self.metric_value_labels["pais_mais_titulos"].configure(text=pais_mais_titulos)

    def _refresh_charts(self) -> None:
        self._plot_type_chart()
        self._plot_release_year_chart()
        self._plot_top_countries_chart()
        self._plot_top_genres_chart()
        self._plot_rating_chart()
        self._plot_year_added_chart()

    def _setup_axis(self, key: str, title: str, xlabel: str = "", ylabel: str = "") -> tuple[Figure, plt.Axes]:
        chart = self.charts[key]
        figure = chart["figure"]
        axis = chart["axis"]
        canvas = chart["canvas"]

        axis.clear()
        axis.set_facecolor(CARD_BG)
        figure.patch.set_facecolor(CARD_BG)
        axis.set_title(title, fontsize=12, fontweight="bold", pad=12)
        if xlabel:
            axis.set_xlabel(xlabel)
        if ylabel:
            axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", alpha=0.18, linestyle="--")
        axis.tick_params(axis="both", colors=TEXT)
        for spine in axis.spines.values():
            spine.set_color("#64748b")
        return figure, axis

    def _draw_empty_chart(self, key: str, title: str, message: str) -> None:
        _, axis = self._setup_axis(key, title)
        axis.set_xticks([])
        axis.set_yticks([])
        axis.text(
            0.5,
            0.5,
            message,
            transform=axis.transAxes,
            ha="center",
            va="center",
            color=MUTED_TEXT,
            fontsize=11,
        )
        self.charts[key]["canvas"].draw_idle()

    def _plot_type_chart(self) -> None:
        counts = (
            self.filtered_df["type"]
            .fillna("Desconhecido")
            .astype(str)
            .str.strip()
            .value_counts()
        )
        counts = counts[[value for value in ["Movie", "TV Show"] if value in counts.index]]
        if counts.empty:
            self._draw_empty_chart("tipo", "Filmes x Séries", "Sem dados para os filtros selecionados.")
            return

        _, axis = self._setup_axis("tipo", "Filmes x Séries", ylabel="Quantidade")
        colors = [ACCENT, ACCENT_2]
        bars = axis.bar(counts.index.tolist(), counts.values.tolist(), color=colors[: len(counts)])
        axis.set_ylim(0, max(counts.values) * 1.25)
        for bar, value in zip(bars, counts.values.tolist(), strict=False):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(counts.values) * 0.04,
                str(int(value)),
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
                color=TEXT,
            )
        self.charts["tipo"]["canvas"].draw_idle()

    def _plot_release_year_chart(self) -> None:
        release_years = pd.to_numeric(self.filtered_df["release_year"], errors="coerce").dropna().astype(int)
        counts = release_years.value_counts().sort_index()
        if counts.empty:
            self._draw_empty_chart(
                "ano_lancamento",
                "Títulos por ano de lançamento",
                "Sem dados para os filtros selecionados.",
            )
            return

        _, axis = self._setup_axis("ano_lancamento", "Títulos por ano de lançamento", xlabel="Ano", ylabel="Quantidade")
        axis.plot(counts.index.tolist(), counts.values.tolist(), color=ACCENT, marker="o", linewidth=2.2)
        axis.fill_between(counts.index.tolist(), counts.values.tolist(), color=ACCENT, alpha=0.15)
        step = max(1, len(counts.index) // 12)
        ticks = counts.index.tolist()[::step]
        axis.set_xticks(ticks)
        axis.set_xticklabels([str(value) for value in ticks], rotation=45, ha="right")
        self.charts["ano_lancamento"]["canvas"].draw_idle()

    def _plot_top_countries_chart(self) -> None:
        countries = (
            self.filtered_df["country"]
            .fillna("Desconhecido")
            .astype(str)
            .str.split(",")
            .explode()
            .str.strip()
        )
        countries = countries[countries.ne("") & countries.ne("Desconhecido") & countries.ne("nan")]
        counts = countries.value_counts().head(10)
        if counts.empty:
            self._draw_empty_chart("paises", "Top 10 países com mais títulos", "Sem dados para os filtros selecionados.")
            return

        counts = counts.sort_values(ascending=True)
        _, axis = self._setup_axis("paises", "Top 10 países com mais títulos", xlabel="Quantidade")
        axis.barh(counts.index.tolist(), counts.values.tolist(), color=SUCCESS)
        axis.invert_yaxis()
        self.charts["paises"]["canvas"].draw_idle()

    def _plot_top_genres_chart(self) -> None:
        genres = (
            self.filtered_df["listed_in"]
            .fillna("Desconhecido")
            .astype(str)
            .str.split(",")
            .explode()
            .str.strip()
        )
        genres = genres[genres.ne("") & genres.ne("Desconhecido") & genres.ne("nan")]
        counts = genres.value_counts().head(10)
        if counts.empty:
            self._draw_empty_chart("generos", "Top 10 gêneros mais comuns", "Sem dados para os filtros selecionados.")
            return

        counts = counts.sort_values(ascending=True)
        _, axis = self._setup_axis("generos", "Top 10 gêneros mais comuns", xlabel="Quantidade")
        axis.barh(counts.index.tolist(), counts.values.tolist(), color=WARN)
        axis.invert_yaxis()
        self.charts["generos"]["canvas"].draw_idle()

    def _plot_rating_chart(self) -> None:
        ratings = (
            self.filtered_df["rating"]
            .fillna("Desconhecido")
            .astype(str)
            .str.strip()
        )
        counts = ratings[ratings.ne("") & ratings.ne("Desconhecido") & ratings.ne("nan")].value_counts()
        if counts.empty:
            self._draw_empty_chart("classificacao", "Classificação indicativa", "Sem dados para os filtros selecionados.")
            return

        counts = counts.sort_values(ascending=False)
        _, axis = self._setup_axis("classificacao", "Classificação indicativa", ylabel="Quantidade")
        axis.bar(counts.index.tolist(), counts.values.tolist(), color=ACCENT_2)
        axis.tick_params(axis="x", rotation=40)
        self.charts["classificacao"]["canvas"].draw_idle()

    def _plot_year_added_chart(self) -> None:
        years_added = pd.to_numeric(self.filtered_df["year_added"], errors="coerce").dropna().astype(int)
        counts = years_added.value_counts().sort_index()
        if counts.empty:
            self._draw_empty_chart("adicionados", "Títulos adicionados por ano", "Sem dados para os filtros selecionados.")
            return

        _, axis = self._setup_axis("adicionados", "Títulos adicionados por ano", xlabel="Ano", ylabel="Quantidade")
        axis.plot(counts.index.tolist(), counts.values.tolist(), color=SUCCESS, marker="o", linewidth=2.2)
        axis.fill_between(counts.index.tolist(), counts.values.tolist(), color=SUCCESS, alpha=0.15)
        step = max(1, len(counts.index) // 12)
        ticks = counts.index.tolist()[::step]
        axis.set_xticks(ticks)
        axis.set_xticklabels([str(value) for value in ticks], rotation=45, ha="right")
        self.charts["adicionados"]["canvas"].draw_idle()

    def _refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.filtered_df.empty:
            return

        table_df = self.filtered_df[DISPLAY_COLUMNS].copy()
        for row in table_df.itertuples(index=False, name=None):
            values = [display_value(value) for value in row]
            self.tree.insert("", "end", values=values)

    def _refresh_status(self) -> None:
        self.status_var.set(
            f"Registros filtrados: {len(self.filtered_df)} | Banco SQLite: {self.dataset.db_path.name}"
        )

    def export_csv_dialog(self) -> None:
        default_name = "netflix_filtrado.csv"
        output_path = filedialog.asksaveasfilename(
            title="Exportar dados filtrados",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV", "*.csv")],
        )
        if not output_path:
            return
        self.export_filtered_data(Path(output_path))
        messagebox.showinfo(APP_TITLE, f"Arquivo exportado com sucesso:\n{output_path}")

    def export_filtered_data(self, output_path: Path) -> Path:
        """Exporta o DataFrame filtrado para CSV sem abrir diálogo."""
        self.filtered_df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    def on_close(self) -> None:
        self.dataset.close()
        self.root.destroy()


def build_app() -> NetflixDashboardApp:
    """Cria o dataset, o banco SQLite e a janela principal."""
    dataset = NetflixDataset(BASE_DIR)
    root = tk.Tk()
    return NetflixDashboardApp(root, dataset)


def main() -> None:
    app = build_app()
    auto_close_ms = os.getenv("NETFLIX_AUTO_CLOSE_MS")
    if auto_close_ms:
        try:
            delay = max(0, int(auto_close_ms))
            app.root.after(delay, app.root.destroy)
        except ValueError:
            pass
    app.root.mainloop()


if __name__ == "__main__":
    main()
