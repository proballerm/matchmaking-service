import matplotlib.pyplot as plt
from typing import List


def plot_wait_times(wait_times: List[float]) -> None:
    """
    Plot histogram of matchmaking wait times.
    """
    if not wait_times:
        print("No wait times to plot.")
        return

    plt.figure()
    plt.hist(wait_times, bins=30)
    plt.xlabel("Wait Time (seconds)")
    plt.ylabel("Number of Players")
    plt.title("Matchmaking Queue Wait Time Distribution")
    plt.show()


def plot_rating_differences(rating_diffs: List[float]) -> None:
    """
    Plot histogram of rating differences in matches.
    """
    if not rating_diffs:
        print("No rating differences to plot.")
        return

    plt.figure()
    plt.hist(rating_diffs, bins=30)
    plt.xlabel("Rating Difference")
    plt.ylabel("Number of Matches")
    plt.title("Match Skill Difference Distribution")
    plt.show()


def plot_threshold_history(thresholds: List[float]) -> None:
    if not thresholds:
        print("No threshold data.")
        return

    plt.figure()
    plt.plot(thresholds)
    plt.xlabel("Simulation Time (seconds)")
    plt.ylabel("Rating Threshold")
    plt.title("Adaptive Matchmaking Threshold Over Time")
    plt.show()