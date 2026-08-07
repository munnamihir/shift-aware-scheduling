"""Rendering only — takes the seat shares and draws the figure."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COHORTS = [
    ("corporate", "Corporate (desk)", "#3B3B58"),
    ("weekend_d", "Weekend crew",     "#4C6FA5"),
    ("swing_b",   "Swing shift",      "#3E9B9B"),
    ("night_c",   "Night shift",      "#6FBF73"),
    ("day_a",     "Day shift",        "#E8B33C"),
]


def draw(results: dict[str, dict[str, float]], path="panel_seats.png"):
    labels = list(results)
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    bottoms = [0.0] * len(labels)

    for key, nice, color in COHORTS:
        vals = [results[l].get(key, 0.0) for l in labels]
        ax.bar(labels, vals, bottom=bottoms, label=nice, color=color,
               width=0.55, edgecolor="white", linewidth=0.8)
        for x, (v, b) in enumerate(zip(vals, bottoms)):
            if v >= 4:
                ax.text(x, b + v / 2, f"{v:.0f}%", ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold")
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    # Call out the finding directly on the figure.
    ax.annotate("0%", xy=(0, 100), xytext=(0, 103), ha="center",
                fontsize=11, fontweight="bold", color="#B8860B")
    ax.text(0, 107, "day shift: structurally excluded", ha="center",
            fontsize=9, color="#B8860B")

    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("share of interview panel seats (%)")
    ax.set_title("Who actually gets to sit on interview panels",
                 fontsize=13, fontweight="bold", pad=14)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08),
              ncol=5, frameon=False, fontsize=9)
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    return path


if __name__ == "__main__":
    # Mihir's confirmed baseline run, 100k interviewers / 2,000 loops.
    draw({
        "Back-to-back\n(industry default)": {
            "corporate": 62.1, "weekend_d": 24.6, "night_c": 8.6,
            "swing_b": 4.7, "day_a": 0.0},
        "Split across days": {
            "corporate": 46.8, "weekend_d": 23.5, "day_a": 15.0,
            "night_c": 7.7, "swing_b": 7.0},
    })
    print("wrote panel_seats.png")
