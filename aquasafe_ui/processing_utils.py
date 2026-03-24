from __future__ import annotations

import pandas as pd


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = out.columns.astype(str).str.strip()
    return out


def find_candidate(columns, candidates):
    lookup = {str(col).casefold(): col for col in columns}
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return None


def parse_dates(series: pd.Series, input_format: str | None, output_format: str) -> pd.Series:
    if input_format:
        parsed = pd.to_datetime(series, format=input_format, errors="coerce")
    else:
        parsed = pd.to_datetime(series, dayfirst=True, errors="coerce")

    missing_mask = parsed.isna() & series.notna()
    if missing_mask.any():
        fallback = pd.to_datetime(series, errors="coerce", dayfirst=True)
        parsed = parsed.fillna(fallback)

    return parsed.dt.strftime(output_format).fillna("")


def normalize_ascii(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.strip()
    )


def blank_series(df: pd.DataFrame) -> pd.Series:
    return pd.Series([""] * len(df), index=df.index, dtype="object")


def safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def choose_series(
    df: pd.DataFrame,
    source_col: str | None,
    typed_value: str,
    fallback: pd.Series,
) -> pd.Series:
    if source_col and source_col != "(none)" and source_col in df.columns:
        return df[source_col]

    if safe_text(typed_value):
        return pd.Series([typed_value] * len(df), index=df.index)

    return fallback


def format_single_date(value, input_format: str | None, output_format: str) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    if input_format:
        parsed = pd.to_datetime(text, format=input_format, errors="coerce")
    else:
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")

    if pd.isna(parsed):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return text

    return parsed.strftime(output_format)


def resolve_export_date_series(
    df: pd.DataFrame,
    detected_date_col: str | None,
    date_source: str | None,
    date_text: str,
    date_input_format: str | None,
    date_output_format: str,
) -> pd.Series:
    typed = safe_text(date_text)
    if typed:
        formatted = format_single_date(typed, date_input_format, date_output_format)
        return pd.Series([formatted] * len(df), index=df.index, dtype="object")

    if date_source == "__detected_date__":
        if detected_date_col and detected_date_col in df.columns:
            return df[detected_date_col].fillna("").astype(str).str.strip()
        return blank_series(df)

    if date_source and date_source != "(none)" and date_source in df.columns:
        return df[date_source].apply(
            lambda v: format_single_date(v, date_input_format, date_output_format)
        )

    return blank_series(df)


def resolve_level3_series(df: pd.DataFrame, level3_source: str, level3_text: str) -> pd.Series:
    if level3_source != "(none)" and level3_source in df.columns:
        return df[level3_source]

    if safe_text(level3_text):
        return pd.Series([level3_text] * len(df), index=df.index)

    if "_generic_id" in df.columns:
        return df["_generic_id"]

    return pd.Series(pd.RangeIndex(start=1, stop=len(df) + 1), index=df.index)


def resolve_description_choice(description_source: str, auto_desc_col: str | None) -> str:
    if description_source == "(auto detected description column)" and auto_desc_col:
        return auto_desc_col
    if description_source == "(auto detected description column)" and not auto_desc_col:
        return "(none)"
    return description_source


def get_passthrough_columns(df: pd.DataFrame, exclude: set[str] | None = None) -> list[str]:
    exclude = {str(c).strip() for c in (exclude or set())}
    passthrough: list[str] = []

    for col in df.columns:
        name = str(col).strip()
        if name == "geometry":
            continue
        if name in exclude:
            continue
        passthrough.append(name)

    return passthrough