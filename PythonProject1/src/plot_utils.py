import pandas as pd
import seaborn as sns

def get_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.select_dtypes(include="number")

def build_corr_matrix(df: pd.DataFrame) -> pd.DataFrame:
    num = get_numeric_df(df)
    if num.shape[1] < 2:
        return pd.DataFrame()
    return num.corr()

def draw_heatmap(ax, corr_df: pd.DataFrame, title: str):
    ax.clear()
    if corr_df.empty:
        ax.set_title("Недостаточно числовых столбцов")
        return
    sns.heatmap(corr_df, ax=ax, annot=True, fmt=".2f")
    ax.set_title(title)

def draw_line(ax, df: pd.DataFrame, column: str):
    ax.clear()
    ax.plot(df.index, df[column])
    ax.set_title(f"Линейный график: {column}")
    ax.set_xlabel("Индекс строки")
    ax.set_ylabel(column)
