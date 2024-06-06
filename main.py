import SingleBlockchainScheme
import PartialHomomorphyScheme
import TwoBlockchainsScheme


def main():
    simulation = PartialHomomorphyScheme.Simulation("nh1", quiet=False, random_speed_log_count=20,
                                                   sleep_time=0.2, traffic_update_interval_in_seconds=30)
    simulation.run()
    print(simulation.get_simulation_data())
    simulation.end_run()


if __name__ == '__main__':
    main()
