import SingleBlockchainScheme
import PartialHomomorphyScheme
import TwoBlockchainsScheme


def main():
    nh = "nh0"
    simulation = PartialHomomorphyScheme.Simulation(nh, "./graphs/" + nh + ".gml", quiet=False,
                                                    random_speed_log_count=100,
                                                    sleep_time=0.1, traffic_update_interval_in_seconds=2, key_size=2048)
    simulation.run()
    print(simulation.get_simulation_data())
    simulation.end_run()


if __name__ == '__main__':
    main()
