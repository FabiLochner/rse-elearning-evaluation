import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.offsetbox import AnchoredText
import seaborn as sns



# Load df with results 

df = pd.read_csv("../df_gpt-4o-mini_2026-01-21_21-38.csv")
print(df.shape)
df.head()


# Filter to successful annotations only
df_valid = df[df["label_research_software"].notna()].copy()
print(df_valid.shape)


# Get descriptive statistics
df_valid["label_research_software"].describe()




# Group by year and calculate means & standard deviations

df_valid.groupby("year")["label_research_software"].mean()

# Create a comprehensive dataframe
df_valid_yearly_stats = df_valid.groupby("year").agg(
    n_papers=("label_research_software", "count"),
    mean_label=("label_research_software", "mean"),
    std_label=("label_research_software", "std"),
    sum_research_sw=("label_research_software", "sum")
    ).round(2)

df_valid_yearly_stats.head()




def add_annotation_box(fig, ax):
    """
    Option 1: Elegant box with subtle teal accent
    Uses fig.text() with custom bbox properties
    """
    annotation_text = (
        "Details of the Experiment (Binary Classification)\n"
        "─────────────────────────────────────────────────\n"
        "LLM Annotation: GPT-4o-mini (temperature: 0)\n"
        "Research Software Definition: Gruenpeter et al. (2021)\n"
        "Error Bars: Standard Deviation  \n"
        "Total Papers: n = 1,052"
    )
    
    # Get the bar color for coordination
    bar_color = sns.color_palette("husl", 9)[5]
    
    # Create a lighter version for the box background
    box_bg_color = (*bar_color[:3], 0.08)  # Very light teal with low alpha
    box_edge_color = (*bar_color[:3], 0.6)  # Teal edge with medium alpha
    
    fig.text(
        0.5, 0.02,  # x, y position (centered, near bottom)
        annotation_text,
        ha='center', va='bottom',
        fontsize=9,
        family='monospace',  # Clean, readable font
        linespacing=1.5,
        bbox=dict(
            boxstyle='round,pad=0.8,rounding_size=0.3',
            facecolor=box_bg_color,
            edgecolor=box_edge_color,
            linewidth=1.5
        )
    )



# ========================================== Make the visualization

# Reset index so 'year' becomes a column (it was the index after groupby)
df_plot = df_valid_yearly_stats.reset_index()

# Set style for presentation
sns.set_theme(context="talk", style="darkgrid")

# Set monospace font globally for the entire figure
plt.rcParams['font.family'] = 'monospace'

fig, ax = plt.subplots(figsize=(14, 7))


BAR_COLOR = sns.color_palette("husl", 9)[5]


# Create bar plot
bars = ax.bar(
    x=df_plot["year"].astype(str),
    height=df_plot["mean_label"],
    color=BAR_COLOR,
    edgecolor="black",
    linewidth=0.5
)

# Add n_papers as text at the BOTTOM of each bar
for bar, n in zip(bars, df_plot["n_papers"]):
    ax.text(
        bar.get_x() + bar.get_width() / 2,  # x position: center of bar
        0.02,                                 # y position: near bottom of bar
        f"n={n}",
        ha="center", va="bottom",
        fontsize=9, fontweight="bold", color="black"
    )

# Add error bars
ax.errorbar(
    x=df_plot["year"].astype(str),
    y=df_plot["mean_label"],
    yerr=df_plot["std_label"],
    fmt="none",
    color="black",
    capsize=2,
    capthick=1.5,
    elinewidth=1.5
)

ax.set_ylabel("Proportion of Research Software", fontsize=14, labelpad = 12)
ax.set_xlabel("Year", fontsize=14, labelpad = 20)
ax.set_title("Research Software in DeLFI Publications (2003-2025)", fontsize=16, weight = "bold", pad = 20)
ax.tick_params(axis='x', labelrotation=45)



plt.tight_layout(rect=[0, 0.15, 1, 1])  # [left, bottom, right, top] - leaves 15% space at bottom

add_annotation_box(fig, ax)  # Elegant teal accent

plt.savefig(
    "llm_annotation_barplot.png",
    dpi=200,                    # Slightly higher for crisp text on large screens
    bbox_inches='tight',        # Essential - includes your annotation box
    facecolor='white',          # Clean white background
    edgecolor='none',           # No border around the image
    pad_inches=0.3,             # Small padding around the figure
    transparent=False           # Solid background (set True if you need transparency)
)

print("Chart saved.")

