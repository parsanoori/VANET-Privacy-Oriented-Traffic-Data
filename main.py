import SingleBlockchainScheme
import PartialHomomorphyScheme
import TwoBlockchainsScheme


def main():
    simulation = FullyHomomorphyScheme.Simulation("nh0", quiet=False, random_speed_log_count=1,
                                                   sleep_time=0.2, update_interval=1, poly_modulus_degree=4096)
    simulation.run()
    print(simulation.get_simulation_data())
    simulation.end_run()


if __name__ == '__main__':
    main()
