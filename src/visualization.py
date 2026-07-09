import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


def plot_time_series(
    df: pd.DataFrame,
    x: str = "Year",
    y: str = "Value",
    title: str = "",
    hue: str = None,
    figsize=(12, 6),
):
    fig, ax = plt.subplots(figsize=figsize)
    if hue:
        for label, group in df.groupby(hue):
            ax.plot(group[x], group[y], label=label, marker="o", markersize=3)
        ax.legend()
    else:
        ax.plot(df[x], df[y], marker="o", markersize=3, linewidth=2)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return fig


def plot_interactive_time_series(
    df: pd.DataFrame,
    x: str = "Year",
    y: str = "Value",
    title: str = "",
    color: str = None,
    hover_data: list = None,
):
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        title=title,
        markers=True,
        hover_data=hover_data,
        template="plotly_white",
    )
    fig.update_layout(
        title_font_size=16,
        xaxis_title_font_size=14,
        yaxis_title_font_size=14,
        hovermode="x unified",
    )
    return fig


def plot_correlation_heatmap(
    df: pd.DataFrame,
    title: str = "Matrice de Corrélation",
    figsize=(10, 8),
):
    numeric = df.select_dtypes(include=[np.number])
    corr = numeric.corr()

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                center=0, square=True, linewidths=1, ax=ax)
    ax.set_title(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return fig


def plot_bar_comparison(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str = "",
    hue: str = None,
    figsize=(12, 6),
):
    fig, ax = plt.subplots(figsize=figsize)
    sns.barplot(data=df, x=x, y=y, hue=hue, ax=ax)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    return fig


def plot_dual_axis(
    df: pd.DataFrame,
    x: str,
    y1: str,
    y2: str,
    label1: str = "",
    label2: str = "",
    title: str = "",
    figsize=(12, 6),
):
    fig, ax1 = plt.subplots(figsize=figsize)
    color1, color2 = "#1f77b4", "#d62728"

    ax1.plot(df[x], df[y1], color=color1, marker="o", label=label1, linewidth=2)
    ax1.set_xlabel(x)
    ax1.set_ylabel(label1, color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2 = ax1.twinx()
    ax2.plot(df[x], df[y2], color=color2, marker="s", label=label2, linewidth=2)
    ax2.set_ylabel(label2, color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    return fig
