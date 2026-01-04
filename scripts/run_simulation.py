from simulation.simulator import MatchmakingSimulator
from simulation.visualize import (
    plot_wait_times,
    plot_rating_differences,
    plot_threshold_history,
)
from simulation.analysis import summarize_simulation


def main():
    sim = MatchmakingSimulator(
        arrival_rate_per_second=0.8,      # increase load to see adaptation
        simulation_duration_seconds=180,  # longer run makes curve clearer
    )

    sim.run()

    # Print quantitative results
    print(summarize_simulation(sim))

    # Visualizations
    plot_wait_times(sim.wait_times)
    plot_rating_differences(sim.rating_diffs)
    plot_threshold_history(sim.threshold_history)


if __name__ == "__main__":
    main()
