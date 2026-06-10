from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


APP_TITLE = "Dashboard Netflix - Storytelling de Dados"
APP_SUBTITLE = (
    "Uma análise visual da evolução do catálogo da Netflix por tipo, país, gênero, ano e classificação."
)
QUESTION = (
    "Como o catálogo da Netflix evoluiu ao longo dos anos e quais padrões aparecem nos tipos de conteúdo, países e gêneros?"
)
DATA_POV = (
    "O catálogo da Netflix não deve ser analisado apenas pela quantidade total de títulos. "
    "A evolução temporal, os países, os gêneros e o tipo de conteúdo ajudam a mostrar como a "
    "plataforma construiu seu catálogo e quais padrões de conteúdo aparecem com mais força."
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "netflix.db"
EXPECTED_TABLES = {
    "titulos",
    "generos",
    "paises",
    "diretores",
    "elenco",
    "classificacoes",
    "linha_temporal",
}

EXPECTED_TITULOS_COLUMNS = [
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
    "year_added",
    "month_added",
    "main_country",
    "decade",
    "content_age",
    "main_genre",
]

DISPLAY_COLUMNS = [
    "title",
    "type",
    "director",
    "main_country",
    "release_year",
    "rating",
    "duration",
    "main_genre",
    "description",
]

SOURCE_HINT_COLUMNS = {
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

COLORS = {
    "bg": "#08111f",
    "panel": "#0e1726",
    "panel_alt": "#111c2e",
    "card": "#132238",
    "border": "rgba(148, 163, 184, 0.18)",
    "text": "#e5eefc",
    "muted": "#9fb0cc",
    "accent": "#5cc8ff",
    "accent_2": "#ffb454",
    "green": "#5fe3a0",
    "red": "#ff7a7a",
    "grid": "rgba(148, 163, 184, 0.18)",
}

CURRENT_YEAR = datetime.now().year


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    f"""
    <style>
    .stApp {{
        background:
            radial-gradient(circle at top left, rgba(92, 200, 255, 0.14), transparent 30%),
            radial-gradient(circle at top right, rgba(255, 180, 84, 0.10), transparent 28%),
            linear-gradient(180deg, {COLORS["bg"]} 0%, #0b1320 100%);
        color: {COLORS["text"]};
    }}
    header[data-testid="stHeader"],
    div[data-testid="stToolbar"],
    #MainMenu,
    footer {{
        visibility: hidden;
        height: 0;
    }}
    .block-container {{
        max-width: 1600px;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
        padding-left: clamp(1rem, 2vw, 2.5rem);
        padding-right: clamp(1rem, 2vw, 2.5rem);
    }}
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS["panel"]} 0%, #0b1320 100%);
        border-right: 1px solid {COLORS["border"]};
    }}
    .story-title {{
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1.05;
        margin-bottom: 0.35rem;
        color: {COLORS["text"]};
    }}
    .story-subtitle {{
        font-size: 1.12rem;
        line-height: 1.7;
        color: {COLORS["muted"]};
        margin-bottom: 0.7rem;
    }}
    .story-callout {{
        background: linear-gradient(180deg, rgba(19, 34, 56, 0.96), rgba(13, 23, 38, 0.9));
        border: 1px solid rgba(92, 200, 255, 0.18);
        border-left: 4px solid {COLORS["accent"]};
        border-radius: 18px;
        padding: 1.05rem 1.15rem;
        margin: 0.8rem 0 1.1rem 0;
        font-size: 1.02rem;
        line-height: 1.75;
        box-shadow: 0 18px 40px rgba(5, 10, 18, 0.26);
    }}
    .story-callout strong {{
        color: {COLORS["text"]};
    }}
    .story-kicker {{
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.74rem;
        color: {COLORS["accent"]};
        margin-bottom: 0.35rem;
        font-weight: 700;
    }}
    .story-section {{
        background: linear-gradient(180deg, rgba(15, 24, 39, 0.94), rgba(10, 16, 27, 0.9));
        border: 1px solid rgba(92, 200, 255, 0.12);
        border-radius: 20px;
        padding: 1.1rem 1.15rem 1rem 1.15rem;
        margin-bottom: 1rem;
        box-shadow: 0 16px 38px rgba(4, 9, 18, 0.24);
    }}
    .story-section h3 {{
        margin-top: 0;
        margin-bottom: 0.35rem;
        color: {COLORS["text"]};
    }}
    .story-section p {{
        color: {COLORS["muted"]};
        margin-bottom: 0;
        font-size: 1.02rem;
        line-height: 1.78;
    }}
    .metric-box {{
        background: linear-gradient(180deg, rgba(22, 39, 63, 0.98), rgba(12, 20, 34, 0.96));
        border: 1px solid rgba(92, 200, 255, 0.22);
        border-radius: 18px;
        padding: 1rem 1.05rem;
        height: 100%;
        box-shadow:
            0 16px 32px rgba(4, 9, 18, 0.26),
            inset 0 1px 0 rgba(255, 255, 255, 0.03);
    }}
    .metric-label {{
        color: {COLORS["muted"]};
        font-size: 0.86rem;
        letter-spacing: 0.035em;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
    }}
    .metric-value {{
        color: #ffffff;
        font-size: clamp(1.95rem, 2.2vw, 2.55rem);
        font-weight: 800;
        line-height: 1.08;
        letter-spacing: -0.04em;
        text-shadow: 0 0 18px rgba(92, 200, 255, 0.08);
    }}
    .metric-detail {{
        color: {COLORS["muted"]};
        font-size: 0.9rem;
        margin-top: 0.4rem;
        line-height: 1.45;
    }}
    div[data-testid="stCaptionContainer"] p {{
        font-size: 0.95rem;
        color: {COLORS["muted"]};
    }}
    div[data-testid="stAlert"] {{
        background: rgba(19, 34, 56, 0.92);
        border: 1px solid rgba(92, 200, 255, 0.16);
        color: {COLORS["text"]};
    }}
    div[data-testid="stAlert"] p {{
        font-size: 1.02rem;
        line-height: 1.7;
        color: {COLORS["text"]};
    }}
    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stMultiSelect label,
    div[data-testid="stSidebar"] .stTextInput label,
    div[data-testid="stSidebar"] .stSlider label {{
        color: {COLORS["text"]} !important;
    }}
    div[data-testid="stMetric"] {{
        background: rgba(19, 34, 56, 0.88);
        border: 1px solid {COLORS["border"]};
        border-radius: 16px;
        padding: 0.3rem 0.5rem;
    }}
    div[data-testid="stMetricLabel"] {{
        color: {COLORS["muted"]};
    }}
    div[data-testid="stMetricValue"] {{
        color: {COLORS["text"]};
    }}
    div[data-testid="stDataFrame"] {{
        border: 1px solid {COLORS["border"]};
        border-radius: 12px;
        overflow: hidden;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def normalize_column_name(name: str) -> str:
    normalized = name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def normalize_text(value) -> str:
    if pd.isna(value):
        return "Desconhecido"
    text = str(value).strip()
    if not text:
        return "Desconhecido"
    if text.lower() in {"nan", "<na>", "none", "null"}:
        return "Desconhecido"
    return text


def clean_text_series(series: pd.Series) -> pd.Series:
    return series.map(normalize_text).astype("string")


def first_value(text: str) -> str:
    text = normalize_text(text)
    if text == "Desconhecido":
        return text
    first = text.split(",")[0].strip()
    return first if first else "Desconhecido"


def parse_duration_minutes(duration: str) -> int | None:
    text = normalize_text(duration)
    if text == "Desconhecido":
        return None
    match = re.search(r"(\d+)\s*min", text.lower())
    return int(match.group(1)) if match else None


def parse_series_seasons(duration: str) -> int | None:
    text = normalize_text(duration)
    if text == "Desconhecido":
        return None
    match = re.search(r"(\d+)\s*season", text.lower())
    return int(match.group(1)) if match else None


def read_csv_header(path: Path) -> list[str]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle)
                return next(reader)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError(f"Não foi possível ler o cabeçalho de {path}")


def score_csv_candidate(path: Path) -> tuple[int, int]:
    try:
        header = read_csv_header(path)
    except Exception:
        return 0, 0

    normalized = {normalize_column_name(column) for column in header}
    matches = len(SOURCE_HINT_COLUMNS & normalized)
    score = matches * 20
    name_lower = path.name.lower()
    if name_lower == "netflix_titles.csv":
        score += 100
    if "netflix" in name_lower:
        score += 30
    return score, matches


def find_source_csv(base_dir: Path) -> Path:
    candidates = sorted(base_dir.glob("*.csv"))
    if not candidates:
        candidates = sorted(base_dir.rglob("*.csv"))
    if not candidates:
        raise FileNotFoundError("Nenhum arquivo CSV foi encontrado na pasta do projeto.")

    scored: list[tuple[int, int, Path]] = []
    for path in candidates:
        score, matches = score_csv_candidate(path)
        if matches:
            scored.append((score, matches, path))

    if not scored:
        raise ValueError(
            "Nenhum CSV compatível com o esquema da Netflix foi encontrado. "
            "Verifique se o arquivo contém colunas como show_id, type, title, date_added e listed_in."
        )

    scored.sort(key=lambda item: (-item[0], -item[1], str(item[2]).lower()))
    return scored[0][2]


def read_csv_robust(path: Path) -> pd.DataFrame:
    attempts = [
        {"encoding": "utf-8-sig", "engine": "c"},
        {"encoding": "utf-8-sig", "engine": "python"},
        {"encoding": "latin-1", "engine": "c"},
        {"encoding": "latin-1", "engine": "python"},
    ]
    last_error: Exception | None = None
    for options in attempts:
        try:
            return pd.read_csv(path, low_memory=False, **options)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError(f"Não foi possível ler o CSV {path.name}")


def explode_table(df: pd.DataFrame, source_column: str, target_column: str) -> pd.DataFrame:
    temp = df[["show_id", "title", source_column]].copy()
    temp[target_column] = (
        temp[source_column]
        .fillna("Desconhecido")
        .astype(str)
        .str.split(",")
    )
    temp = temp.explode(target_column)
    temp[target_column] = temp[target_column].map(normalize_text)
    temp = temp.loc[temp[target_column] != "Desconhecido", ["show_id", "title", target_column]]
    temp = temp.drop_duplicates().reset_index(drop=True)
    return temp


def build_clean_tables(raw_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    df = raw_df.copy()
    df.columns = [normalize_column_name(column) for column in df.columns]

    required_columns = [
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
    ]
    for column in required_columns:
        if column not in df.columns:
            df[column] = pd.NA

    df = df[required_columns].copy()
    for column in ["show_id", "type", "title", "director", "cast", "country", "rating", "duration", "listed_in", "description"]:
        df[column] = clean_text_series(df[column])

    df = df.drop_duplicates(subset=["show_id"], keep="first").reset_index(drop=True)
    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce").astype("Int64")

    date_added = pd.to_datetime(df["date_added"], errors="coerce")
    df["date_added"] = date_added.dt.strftime("%Y-%m-%d").fillna("Desconhecido")
    df["year_added"] = date_added.dt.year.astype("Int64")
    df["month_added"] = date_added.dt.month.astype("Int64")

    df["main_country"] = df["country"].map(first_value)
    df["main_genre"] = df["listed_in"].map(first_value)
    df["decade"] = (df["release_year"] // 10 * 10).astype("Int64")
    df["content_age"] = (CURRENT_YEAR - df["release_year"]).astype("Int64")

    titulos = df[
        [
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
            "year_added",
            "month_added",
            "main_country",
            "decade",
            "content_age",
            "main_genre",
        ]
    ].copy()

    generos = explode_table(df, "listed_in", "genero")
    paises = explode_table(df, "country", "pais")
    diretores = explode_table(df, "director", "diretor")
    elenco = explode_table(df, "cast", "ator")

    classificacoes = (
        titulos["rating"]
        .map(normalize_text)
        .value_counts(dropna=False)
        .rename_axis("rating")
        .reset_index(name="quantidade")
        .sort_values(["quantidade", "rating"], ascending=[False, True])
        .reset_index(drop=True)
    )

    timeline = (
        titulos.loc[titulos["release_year"].notna()]
        .assign(release_year_num=lambda frame: frame["release_year"].astype(int))
        .groupby("release_year_num", as_index=False)
        .agg(
            total_titulos=("show_id", "size"),
            total_filmes=("type", lambda s: int((s == "Movie").sum())),
            total_series=("type", lambda s: int((s == "TV Show").sum())),
        )
        .rename(columns={"release_year_num": "ano"})
        .sort_values("ano")
        .reset_index(drop=True)
    )

    return {
        "titulos": titulos,
        "generos": generos,
        "paises": paises,
        "diretores": diretores,
        "elenco": elenco,
        "classificacoes": classificacoes,
        "linha_temporal": timeline,
    }


def expected_titulos_columns() -> list[str]:
    return EXPECTED_TITULOS_COLUMNS


def database_has_expected_schema(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            existing_tables = {
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            if not EXPECTED_TABLES.issubset(existing_tables):
                return False

            titulos_columns = [row[1] for row in conn.execute("PRAGMA table_info(titulos)")]
            if titulos_columns != expected_titulos_columns():
                return False

            def table_columns(table_name: str) -> list[str]:
                return [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]

            if table_columns("generos") != ["show_id", "title", "genero"]:
                return False
            if table_columns("paises") != ["show_id", "title", "pais"]:
                return False
            if table_columns("diretores") != ["show_id", "title", "diretor"]:
                return False
            if table_columns("elenco") != ["show_id", "title", "ator"]:
                return False
            if table_columns("classificacoes") != ["rating", "quantidade"]:
                return False
            if table_columns("linha_temporal") != ["ano", "total_titulos", "total_filmes", "total_series"]:
                return False
        return True
    except sqlite3.Error:
        return False


def database_matches_tables(db_path: Path, tables: dict[str, pd.DataFrame]) -> bool:
    if not db_path.exists():
        return False
    try:
        with sqlite3.connect(db_path) as conn:
            for table_name, table_df in tables.items():
                existing_count = conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                if existing_count != len(table_df):
                    return False
        return True
    except sqlite3.Error:
        return False


def write_database(db_path: Path, tables: dict[str, pd.DataFrame]) -> None:
    with sqlite3.connect(db_path) as conn:
        for table_name, table_df in tables.items():
            table_df.to_sql(table_name, conn, if_exists="replace", index=False)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_show_id ON titulos(show_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_type ON titulos(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_release_year ON titulos(release_year)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_rating ON titulos(rating)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generos_show_id ON generos(show_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_paises_show_id ON paises(show_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_diretores_show_id ON diretores(show_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_elenco_show_id ON elenco(show_id)")


@st.cache_data(show_spinner=True)
def load_project_tables(csv_path_str: str, csv_mtime: float) -> dict[str, pd.DataFrame]:
    raw_df = read_csv_robust(Path(csv_path_str))
    return build_clean_tables(raw_df)


def ensure_database(db_path: Path, tables: dict[str, pd.DataFrame], source_mtime: float) -> None:
    needs_refresh = (
        not db_path.exists()
        or not database_has_expected_schema(db_path)
        or db_path.stat().st_mtime < source_mtime
        or not database_matches_tables(db_path, tables)
    )
    if needs_refresh:
        write_database(db_path, tables)


def load_project() -> dict[str, object]:
    source_csv = find_source_csv(BASE_DIR)
    source_mtime = source_csv.stat().st_mtime
    tables = load_project_tables(str(source_csv), source_mtime)
    ensure_database(DB_PATH, tables, source_mtime)

    project = {
        "source_csv": source_csv,
        "database_path": DB_PATH,
        "tables": tables,
        "titles": tables["titulos"],
        "genres": tables["generos"],
        "countries": tables["paises"],
        "directors": tables["diretores"],
        "cast": tables["elenco"],
        "ratings": tables["classificacoes"],
        "timeline": tables["linha_temporal"],
    }
    return project


def extract_filtered_ids(table: pd.DataFrame, column: str, selected_value: str) -> set[str]:
    if selected_value == "Todos":
        return set()
    return set(table.loc[table[column] == selected_value, "show_id"].astype(str))


def apply_filters(
    titles: pd.DataFrame,
    countries: pd.DataFrame,
    genres: pd.DataFrame,
    type_filter: str,
    country_filter: str,
    genre_filter: str,
    rating_filter: str,
    release_year_range: tuple[int, int] | None,
    added_year_range: tuple[int, int] | None,
    search_term: str,
) -> pd.DataFrame:
    filtered = titles.copy()

    if type_filter != "Todos":
        filtered = filtered.loc[filtered["type"] == type_filter]

    if country_filter != "Todos":
        ids = extract_filtered_ids(countries, "pais", country_filter)
        filtered = filtered.loc[filtered["show_id"].astype(str).isin(ids)]

    if genre_filter != "Todos":
        ids = extract_filtered_ids(genres, "genero", genre_filter)
        filtered = filtered.loc[filtered["show_id"].astype(str).isin(ids)]

    if rating_filter != "Todos":
        filtered = filtered.loc[filtered["rating"] == rating_filter]

    if release_year_range is not None:
        start_year, end_year = release_year_range
        release_year = pd.to_numeric(filtered["release_year"], errors="coerce")
        filtered = filtered.loc[release_year.between(start_year, end_year, inclusive="both")]

    if added_year_range is not None:
        start_year, end_year = added_year_range
        year_added = pd.to_numeric(filtered["year_added"], errors="coerce")
        filtered = filtered.loc[year_added.between(start_year, end_year, inclusive="both")]

    search_term = search_term.strip().lower()
    if search_term:
        filtered = filtered.loc[filtered["title"].str.lower().str.contains(search_term, na=False)]

    return filtered.reset_index(drop=True)


def safe_mode_value(series: pd.Series, fallback: str = "Desconhecido") -> str:
    cleaned = series.map(normalize_text)
    cleaned = cleaned.loc[cleaned != "Desconhecido"]
    if cleaned.empty:
        return fallback
    return cleaned.value_counts().idxmax()


def get_metrics(filtered: pd.DataFrame, countries: pd.DataFrame, genres: pd.DataFrame) -> dict[str, str]:
    non_unknown_countries = countries.loc[countries["pais"] != "Desconhecido", "pais"]
    non_unknown_genres = genres.loc[genres["genero"] != "Desconhecido", "genero"]
    release_years = pd.to_numeric(filtered["release_year"], errors="coerce").dropna()
    year_added = pd.to_numeric(filtered["year_added"], errors="coerce").dropna()
    decade = pd.to_numeric(filtered["decade"], errors="coerce").dropna()

    return {
        "total_titulos": f"{len(filtered):,}".replace(",", "."),
        "total_filmes": f"{int((filtered['type'] == 'Movie').sum()):,}".replace(",", "."),
        "total_series": f"{int((filtered['type'] == 'TV Show').sum()):,}".replace(",", "."),
        "total_paises": f"{int(non_unknown_countries.nunique()):,}".replace(",", "."),
        "total_generos": f"{int(non_unknown_genres.nunique()):,}".replace(",", "."),
        "ano_mais_antigo": str(int(release_years.min())) if not release_years.empty else "Desconhecido",
        "ano_mais_recente": str(int(release_years.max())) if not release_years.empty else "Desconhecido",
        "pais_mais_frequente": safe_mode_value(filtered["main_country"]),
        "genero_mais_frequente": safe_mode_value(filtered["main_genre"]),
        "ano_mais_titulos": str(int(release_years.value_counts().idxmax())) if not release_years.empty else "Desconhecido",
        "decada_mais_forte": str(int(decade.value_counts().idxmax())) if not decade.empty else "Desconhecido",
        "ano_mais_recente_adicionado": str(int(year_added.max())) if not year_added.empty else "Desconhecido",
    }


def story_card(label: str, value: str, detail: str = "") -> str:
    return f"""
    <div class="metric-box">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {f'<div class="metric-detail">{detail}</div>' if detail else ''}
    </div>
    """


def render_metric_grid(metrics: dict[str, str]) -> None:
    rows = [
        [
            ("Total de títulos", metrics["total_titulos"], "Catálogo filtrado"),
            ("Total de filmes", metrics["total_filmes"], "Parte do catálogo"),
            ("Total de séries", metrics["total_series"], "Parte do catálogo"),
        ],
        [
            ("Total de países", metrics["total_paises"], "Países distintos"),
            ("Total de gêneros", metrics["total_generos"], "Gêneros distintos"),
            ("Ano mais antigo", metrics["ano_mais_antigo"], "Primeiro lançamento"),
        ],
        [
            ("Ano mais recente", metrics["ano_mais_recente"], "Último lançamento"),
            ("País mais frequente", metrics["pais_mais_frequente"], "No catálogo filtrado"),
            ("Gênero mais frequente", metrics["genero_mais_frequente"], "No catálogo filtrado"),
        ],
    ]
    for row in rows:
        cols = st.columns(3, gap="large")
        for col, (label, value, detail) in zip(cols, row, strict=False):
            with col:
                st.markdown(story_card(label, value, detail), unsafe_allow_html=True)


def plot_timeline_figures(filtered: pd.DataFrame) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    release = (
        filtered.loc[filtered["release_year"].notna()]
        .assign(release_year_num=lambda frame: frame["release_year"].astype(int))
        .groupby("release_year_num", as_index=False)
        .size()
        .rename(columns={"size": "total"})
        .sort_values("release_year_num")
    )

    added = (
        filtered.loc[filtered["year_added"].notna()]
        .assign(year_added_num=lambda frame: frame["year_added"].astype(int))
        .groupby("year_added_num", as_index=False)
        .size()
        .rename(columns={"size": "total"})
        .sort_values("year_added_num")
    )

    comparative = (
        filtered.loc[filtered["release_year"].notna()]
        .assign(release_year_num=lambda frame: frame["release_year"].astype(int))
        .groupby(["release_year_num", "type"], as_index=False)
        .size()
        .pivot(index="release_year_num", columns="type", values="size")
        .fillna(0)
        .reset_index()
        .sort_values("release_year_num")
    )
    if "Movie" not in comparative.columns:
        comparative["Movie"] = 0
    if "TV Show" not in comparative.columns:
        comparative["TV Show"] = 0

    decade = (
        filtered.loc[filtered["decade"].notna()]
        .assign(decade_num=lambda frame: frame["decade"].astype(int))
        .groupby("decade_num", as_index=False)
        .size()
        .rename(columns={"size": "total"})
        .sort_values("decade_num")
    )

    if release.empty:
        fig_release = empty_figure("Títulos por ano de lançamento", "Sem dados para os filtros selecionados.")
    else:
        fig_release = px.line(
            release,
            x="release_year_num",
            y="total",
            markers=True,
            title="Títulos por ano de lançamento",
        )
        fig_release.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_release.update_traces(line=dict(color=COLORS["accent"], width=3), marker=dict(size=8))
        fig_release.update_xaxes(title="Ano de lançamento")
        fig_release.update_yaxes(title="Quantidade")

    if added.empty:
        fig_added = empty_figure("Títulos adicionados por ano na Netflix", "Sem dados para os filtros selecionados.")
    else:
        fig_added = px.line(
            added,
            x="year_added_num",
            y="total",
            markers=True,
            title="Títulos adicionados por ano na Netflix",
        )
        fig_added.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_added.update_traces(line=dict(color=COLORS["accent_2"], width=3), marker=dict(size=8))
        fig_added.update_xaxes(title="Ano de entrada na Netflix")
        fig_added.update_yaxes(title="Quantidade")

    if comparative.empty:
        fig_compare = empty_figure("Filmes x Séries ao longo dos anos", "Sem dados para os filtros selecionados.")
    else:
        fig_compare = go.Figure()
        fig_compare.add_trace(
            go.Scatter(
                x=comparative["release_year_num"],
                y=comparative["Movie"],
                mode="lines+markers",
                name="Movies",
                line=dict(color=COLORS["accent"], width=3),
            )
        )
        fig_compare.add_trace(
            go.Scatter(
                x=comparative["release_year_num"],
                y=comparative["TV Show"],
                mode="lines+markers",
                name="TV Shows",
                line=dict(color=COLORS["accent_2"], width=3),
            )
        )
        fig_compare.update_layout(
            title="Filmes x Séries ao longo dos anos",
            template="plotly_dark",
            paper_bgcolor=COLORS["panel"],
            plot_bgcolor=COLORS["panel"],
            legend_title_text="Tipo",
        )
        fig_compare.update_xaxes(title="Ano de lançamento")
        fig_compare.update_yaxes(title="Quantidade")

    if decade.empty:
        fig_decade = empty_figure("Quantidade por década", "Sem dados para os filtros selecionados.")
    else:
        fig_decade = px.bar(
            decade,
            x="decade_num",
            y="total",
            title="Quantidade por década",
        )
        fig_decade.update_traces(marker_color=COLORS["green"])
        fig_decade.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_decade.update_xaxes(title="Década")
        fig_decade.update_yaxes(title="Quantidade")

    return fig_release, fig_added, fig_compare, fig_decade


def plot_profile_figures(filtered: pd.DataFrame) -> tuple[go.Figure, go.Figure, go.Figure, go.Figure]:
    type_counts = filtered["type"].map(normalize_text).value_counts()
    type_counts = type_counts[[value for value in ["Movie", "TV Show"] if value in type_counts.index]]
    if type_counts.empty:
        fig_type = empty_figure("Proporção entre filmes e séries", "Sem dados para os filtros selecionados.")
    else:
        fig_type = go.Figure(
            data=[
                go.Pie(
                    labels=type_counts.index.tolist(),
                    values=type_counts.values.tolist(),
                    hole=0.55,
                    marker=dict(colors=[COLORS["accent"], COLORS["accent_2"]]),
                    textinfo="percent+label",
                )
            ]
        )
        fig_type.update_layout(
            title="Proporção entre filmes e séries",
            template="plotly_dark",
            paper_bgcolor=COLORS["panel"],
            plot_bgcolor=COLORS["panel"],
            showlegend=False,
        )

    country_series = (
        filtered["country"]
        .fillna("Desconhecido")
        .astype(str)
        .str.split(",")
        .explode()
        .map(normalize_text)
    )
    country_series = country_series.loc[country_series != "Desconhecido"]
    top_countries = country_series.value_counts().head(10)
    if top_countries.empty:
        fig_countries = empty_figure("Top 10 países", "Sem dados para os filtros selecionados.")
    else:
        countries_df = top_countries.sort_values(ascending=True).reset_index()
        countries_df.columns = ["pais", "quantidade"]
        fig_countries = px.bar(
            countries_df,
            x="quantidade",
            y="pais",
            orientation="h",
            title="Top 10 países com mais títulos",
        )
        fig_countries.update_traces(marker_color=COLORS["accent"])
        fig_countries.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_countries.update_xaxes(title="Quantidade")
        fig_countries.update_yaxes(title="")

    genre_series = (
        filtered["listed_in"]
        .fillna("Desconhecido")
        .astype(str)
        .str.split(",")
        .explode()
        .map(normalize_text)
    )
    genre_series = genre_series.loc[genre_series != "Desconhecido"]
    top_genres = genre_series.value_counts().head(10)
    if top_genres.empty:
        fig_genres = empty_figure("Top 10 gêneros", "Sem dados para os filtros selecionados.")
    else:
        genres_df = top_genres.sort_values(ascending=True).reset_index()
        genres_df.columns = ["genero", "quantidade"]
        fig_genres = px.bar(
            genres_df,
            x="quantidade",
            y="genero",
            orientation="h",
            title="Top 10 gêneros mais comuns",
        )
        fig_genres.update_traces(marker_color=COLORS["accent_2"])
        fig_genres.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_genres.update_xaxes(title="Quantidade")
        fig_genres.update_yaxes(title="")

    rating_counts = filtered["rating"].map(normalize_text).value_counts()
    rating_counts = rating_counts.loc[rating_counts.index != "Desconhecido"]
    if rating_counts.empty:
        fig_rating = empty_figure("Classificação indicativa", "Sem dados para os filtros selecionados.")
    else:
        rating_df = rating_counts.reset_index()
        rating_df.columns = ["rating", "quantidade"]
        fig_rating = px.bar(
            rating_df,
            x="rating",
            y="quantidade",
            title="Classificação indicativa",
        )
        fig_rating.update_traces(marker_color=COLORS["green"])
        fig_rating.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_rating.update_xaxes(title="")
        fig_rating.update_yaxes(title="Quantidade")

    return fig_type, fig_countries, fig_genres, fig_rating


def plot_duration_figures(filtered: pd.DataFrame) -> tuple[go.Figure, go.Figure]:
    movie_minutes = filtered.loc[filtered["type"] == "Movie", "duration"].map(parse_duration_minutes).dropna()
    series_seasons = filtered.loc[filtered["type"] == "TV Show", "duration"].map(parse_series_seasons).dropna()

    if movie_minutes.empty:
        fig_movie_duration = empty_figure("Distribuição de duração dos filmes", "Sem dados para os filtros selecionados.")
    else:
        movie_df = pd.DataFrame({"minutos": movie_minutes.astype(int)})
        fig_movie_duration = px.histogram(
            movie_df,
            x="minutos",
            nbins=min(25, max(10, movie_df["minutos"].nunique())),
            title="Distribuição de duração dos filmes",
        )
        fig_movie_duration.update_traces(marker_color=COLORS["accent"])
        fig_movie_duration.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_movie_duration.update_xaxes(title="Minutos")
        fig_movie_duration.update_yaxes(title="Quantidade")

    if series_seasons.empty:
        fig_series_duration = empty_figure("Quantidade de temporadas das séries", "Sem dados para os filtros selecionados.")
    else:
        series_df = series_seasons.value_counts().sort_index().reset_index()
        series_df.columns = ["temporadas", "quantidade"]
        fig_series_duration = px.bar(
            series_df,
            x="temporadas",
            y="quantidade",
            title="Quantidade de temporadas das séries",
        )
        fig_series_duration.update_traces(marker_color=COLORS["accent_2"])
        fig_series_duration.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
        fig_series_duration.update_xaxes(title="Temporadas")
        fig_series_duration.update_yaxes(title="Quantidade")

    return fig_movie_duration, fig_series_duration


def plot_scatter_figure(filtered: pd.DataFrame) -> go.Figure:
    movies = filtered.loc[filtered["type"] == "Movie"].copy()
    movies["duration_minutes"] = movies["duration"].map(parse_duration_minutes)
    movies = movies.loc[movies["duration_minutes"].notna() & movies["release_year"].notna()]

    if movies.empty:
        return empty_figure(
            "Relação entre ano de lançamento e duração dos filmes",
            "Sem dados para os filtros selecionados.",
        )

    movies["release_year"] = movies["release_year"].astype(int)
    movies["duration_minutes"] = movies["duration_minutes"].astype(int)
    movies["rating"] = movies["rating"].map(normalize_text)
    movies["main_genre"] = movies["main_genre"].map(normalize_text)

    fig = px.scatter(
        movies,
        x="release_year",
        y="duration_minutes",
        color="rating",
        hover_data={
            "title": True,
            "main_country": True,
            "main_genre": True,
            "duration": True,
            "release_year": True,
        },
        title="Relação entre ano de lançamento e duração dos filmes",
    )
    fig.update_traces(marker=dict(size=10, opacity=0.82))
    fig.update_layout(template="plotly_dark", paper_bgcolor=COLORS["panel"], plot_bgcolor=COLORS["panel"])
    fig.update_xaxes(title="Ano de lançamento")
    fig.update_yaxes(title="Duração em minutos")
    return fig


def empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=title,
        template="plotly_dark",
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            dict(
                text=message,
                x=0.5,
                y=0.5,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color=COLORS["muted"], size=14),
            )
        ],
    )
    return fig


def format_period_label(label: str, value: int | None) -> str:
    if value is None or pd.isna(value):
        return label
    return f"{label}: {int(value)}"


def build_conclusion(filtered: pd.DataFrame) -> list[str]:
    if filtered.empty:
        return [
            "Não há registros suficientes nos filtros atuais para gerar uma conclusão automática.",
            "Experimente ampliar os intervalos de ano ou remover algum filtro lateral.",
        ]

    release_years = pd.to_numeric(filtered["release_year"], errors="coerce").dropna()
    decade = pd.to_numeric(filtered["decade"], errors="coerce").dropna()
    titles_by_year = release_years.value_counts()

    type_counts = filtered["type"].map(normalize_text).value_counts()
    type_counts = type_counts.loc[type_counts.index != "Desconhecido"]
    top_type = type_counts.idxmax() if not type_counts.empty else "Desconhecido"

    country_series = (
        filtered["country"]
        .fillna("Desconhecido")
        .astype(str)
        .str.split(",")
        .explode()
        .map(normalize_text)
    )
    country_series = country_series.loc[country_series != "Desconhecido"]
    top_country = country_series.value_counts().idxmax() if not country_series.empty else "Desconhecido"

    genre_series = (
        filtered["listed_in"]
        .fillna("Desconhecido")
        .astype(str)
        .str.split(",")
        .explode()
        .map(normalize_text)
    )
    genre_series = genre_series.loc[genre_series != "Desconhecido"]
    top_genre = genre_series.value_counts().idxmax() if not genre_series.empty else "Desconhecido"

    top_year = int(titles_by_year.idxmax()) if not titles_by_year.empty else None
    top_decade = int(decade.value_counts().idxmax()) if not decade.empty else None

    return [
        f"O tipo de conteúdo mais comum é {top_type}.",
        f"O país mais presente no catálogo é {top_country}.",
        f"O gênero mais comum é {top_genre}.",
        f"O ano com mais títulos lançados foi {top_year}." if top_year is not None else "Não foi possível identificar um ano de pico para os lançamentos.",
        f"A plataforma possui maior concentração de conteúdos da década de {top_decade}." if top_decade is not None else "Não foi possível identificar a década dominante do catálogo.",
    ]


def sidebar_filters(project: dict[str, object]) -> dict[str, object]:
    titles: pd.DataFrame = project["titles"]  # type: ignore[assignment]
    countries: pd.DataFrame = project["countries"]  # type: ignore[assignment]
    genres: pd.DataFrame = project["genres"]  # type: ignore[assignment]

    st.sidebar.title("Filtros")
    st.sidebar.caption("Os filtros são aplicados a toda a narrativa visual.")

    type_options = ["Todos"] + sorted(
        [value for value in titles["type"].map(normalize_text).unique().tolist() if value != "Desconhecido"]
    )
    country_options = ["Todos"] + sorted(
        [value for value in countries["pais"].map(normalize_text).unique().tolist() if value != "Desconhecido"]
    )
    genre_options = ["Todos"] + sorted(
        [value for value in genres["genero"].map(normalize_text).unique().tolist() if value != "Desconhecido"]
    )
    rating_options = ["Todos"] + sorted(
        [value for value in titles["rating"].map(normalize_text).unique().tolist() if value != "Desconhecido"]
    )

    release_years = pd.to_numeric(titles["release_year"], errors="coerce").dropna()
    added_years = pd.to_numeric(titles["year_added"], errors="coerce").dropna()
    if release_years.empty:
        min_release, max_release = CURRENT_YEAR, CURRENT_YEAR
    else:
        min_release, max_release = int(release_years.min()), int(release_years.max())
    if added_years.empty:
        min_added, max_added = CURRENT_YEAR, CURRENT_YEAR
    else:
        min_added, max_added = int(added_years.min()), int(added_years.max())

    if "type_filter" not in st.session_state:
        st.session_state.type_filter = "Todos"
    if "country_filter" not in st.session_state:
        st.session_state.country_filter = "Todos"
    if "genre_filter" not in st.session_state:
        st.session_state.genre_filter = "Todos"
    if "rating_filter" not in st.session_state:
        st.session_state.rating_filter = "Todos"
    if "release_range" not in st.session_state:
        st.session_state.release_range = (min_release, max_release)
    if "added_range" not in st.session_state:
        st.session_state.added_range = (min_added, max_added)
    if "search_term" not in st.session_state:
        st.session_state.search_term = ""

    st.sidebar.selectbox("Tipo", type_options, key="type_filter")
    st.sidebar.selectbox("País", country_options, key="country_filter")
    st.sidebar.selectbox("Gênero", genre_options, key="genre_filter")
    st.sidebar.selectbox("Classificação indicativa", rating_options, key="rating_filter")
    st.sidebar.slider(
        "Intervalo de ano de lançamento",
        min_release,
        max_release,
        key="release_range",
    )
    st.sidebar.slider(
        "Intervalo de ano adicionado na Netflix",
        min_added,
        max_added,
        key="added_range",
    )
    st.sidebar.text_input("Busca por título", placeholder="Digite parte do nome", key="search_term")

    if st.sidebar.button("Limpar filtros", use_container_width=True):
        st.session_state.type_filter = "Todos"
        st.session_state.country_filter = "Todos"
        st.session_state.genre_filter = "Todos"
        st.session_state.rating_filter = "Todos"
        st.session_state.release_range = (min_release, max_release)
        st.session_state.added_range = (min_added, max_added)
        st.session_state.search_term = ""
        st.rerun()

    return {
        "type_filter": st.session_state.type_filter,
        "country_filter": st.session_state.country_filter,
        "genre_filter": st.session_state.genre_filter,
        "rating_filter": st.session_state.rating_filter,
        "release_range": st.session_state.release_range,
        "added_range": st.session_state.added_range,
        "search_term": st.session_state.search_term,
    }


def render_header(project: dict[str, object]) -> None:
    source_csv: Path = project["source_csv"]  # type: ignore[assignment]
    st.markdown(f'<div class="story-kicker">Tema: Análise do catálogo da Netflix</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="story-title">{APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="story-subtitle">{APP_SUBTITLE}</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="story-callout">
            <strong>Pergunta central</strong><br>
            {QUESTION}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="story-callout">
            <strong>Tese / Data POV</strong><br>
            {DATA_POV}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"CSV detectado automaticamente: {source_csv.name} | Banco SQLite: {DB_PATH.name}")


def render_story_intro() -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>1. Contexto da análise</h3>
            <p>
                A Netflix possui filmes e séries de vários países, gêneros, anos e classificações.
                O objetivo aqui não é apenas contar títulos, mas entender como o catálogo evoluiu
                e quais padrões aparecem com mais força no tempo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_timeline_section(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>2. Linha Temporal do Catálogo</h3>
            <p>
                Esta seção responde à pergunta central da análise. A leitura temporal ajuda a identificar
                se o catálogo está concentrado em produções recentes ou se mantém uma presença forte de títulos antigos.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    fig_release, fig_added, fig_compare, fig_decade = plot_timeline_figures(filtered)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(fig_release, use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.plotly_chart(fig_added, use_container_width=True, config={"displayModeBar": False})
    c3, c4 = st.columns(2, gap="large")
    with c3:
        st.plotly_chart(fig_compare, use_container_width=True, config={"displayModeBar": False})
    with c4:
        st.plotly_chart(fig_decade, use_container_width=True, config={"displayModeBar": False})
    st.info("Este gráfico mostra se o catálogo está concentrado em produções recentes ou se possui forte presença de títulos antigos.")


def render_profile_section(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>3. Perfil do catálogo</h3>
            <p>
                Aqui observamos a composição do catálogo: quantos filmes e séries existem, de onde eles vêm,
                quais gêneros dominam e como as classificações indicativas se distribuem.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    fig_type, fig_countries, fig_genres, fig_rating = plot_profile_figures(filtered)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(fig_type, use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.plotly_chart(fig_countries, use_container_width=True, config={"displayModeBar": False})
    c3, c4 = st.columns(2, gap="large")
    with c3:
        st.plotly_chart(fig_genres, use_container_width=True, config={"displayModeBar": False})
    with c4:
        st.plotly_chart(fig_rating, use_container_width=True, config={"displayModeBar": False})


def render_duration_section(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>4. Análise de duração</h3>
            <p>
                A duração ajuda a diferenciar o comportamento de filmes e séries. Filmes costumam ser analisados em minutos,
                enquanto séries são observadas pelo número de temporadas.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    fig_movie_duration, fig_series_duration = plot_duration_figures(filtered)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(fig_movie_duration, use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.plotly_chart(fig_series_duration, use_container_width=True, config={"displayModeBar": False})


def render_scatter_section(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>5. Relações entre variáveis</h3>
            <p>
                O gráfico de dispersão ajuda a visualizar possíveis relações entre ano de lançamento e duração dos filmes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(plot_scatter_figure(filtered), use_container_width=True, config={"displayModeBar": False})
    st.caption(
        "O gráfico de dispersão ajuda a visualizar possíveis relações entre ano de lançamento e duração dos filmes."
    )


def render_table_section(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>6. Tabela interativa</h3>
            <p>
                A tabela abaixo mostra os dados filtrados com os principais campos usados na narrativa e na exploração do catálogo.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    table_df = filtered[DISPLAY_COLUMNS].copy()
    st.dataframe(table_df, use_container_width=True, hide_index=True, height=420)

    csv_bytes = filtered.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label="Baixar dados filtrados em CSV",
        data=csv_bytes,
        file_name="netflix_filtrado.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_conclusion(filtered: pd.DataFrame) -> None:
    st.markdown(
        """
        <div class="story-section">
            <h3>7. Conclusão da Análise</h3>
            <p>
                A conclusão é gerada automaticamente a partir dos dados filtrados, para transformar as evidências em uma leitura executiva.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bullets = build_conclusion(filtered)
    conclusion_html = "".join([f"<li>{bullet}</li>" for bullet in bullets])
    st.markdown(
        f"""
        <div class="story-callout">
            <ul style="margin: 0; padding-left: 1.2rem; color: {COLORS["text"]};">
                {conclusion_html}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    project = load_project()
    render_header(project)
    render_story_intro()

    filters = sidebar_filters(project)
    titles: pd.DataFrame = project["titles"]  # type: ignore[assignment]
    countries: pd.DataFrame = project["countries"]  # type: ignore[assignment]
    genres: pd.DataFrame = project["genres"]  # type: ignore[assignment]

    filtered = apply_filters(
        titles=titles,
        countries=countries,
        genres=genres,
        type_filter=filters["type_filter"],
        country_filter=filters["country_filter"],
        genre_filter=filters["genre_filter"],
        rating_filter=filters["rating_filter"],
        release_year_range=filters["release_range"],
        added_year_range=filters["added_range"],
        search_term=filters["search_term"],
    )

    metrics = get_metrics(filtered, countries, genres)
    render_metric_grid(metrics)
    st.markdown(
        f"""
        <div class="story-callout">
            <strong>Resumo da leitura atual</strong><br>
            Catálogo filtrado com {metrics["total_titulos"]} títulos. O eixo temporal e o perfil do catálogo mudam conforme os filtros laterais.
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_timeline_section(filtered)
    render_profile_section(filtered)
    render_duration_section(filtered)
    render_scatter_section(filtered)
    render_table_section(filtered)
    render_conclusion(filtered)


if __name__ == "__main__":
    main()
