import traci
import time

# Path to your SUMO configuration file
SUMO_CFG = "./osm.sumocfg"

def run_simulation():
    # Start SUMO using the configuration file
    traci.start(["sumo", "-c", SUMO_CFG])
    
    simulation_time_step = 0
    interval = 10  # Interval in seconds
    
    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()  # Advance the simulation by one step
            
            execute_every_interval(simulation_time_step)
            
            simulation_time_step += 1
            time.sleep(1)  # Pause for real-time simulation
    except Exception as e:
        print(f"Error during simulation: {e}")
    finally:
        traci.close()  # Close SUMO connection


def execute_every_interval(simulation_time_step):
    print(f"Executing custom code at simulation time {simulation_time_step} seconds")
    # Retrieve and print the location of all vehicles
    vehicle_ids = traci.vehicle.getIDList()
    if not vehicle_ids:
        print("No vehicles in the simulation at this step.")
        return

    for veh_id in vehicle_ids:
        speed_m_s = traci.vehicle.getSpeed(veh_id)  # Speed in m/s
        speed_kmh = speed_m_s * 3.6  # Convert to km/h
        position = traci.vehicle.getPosition(veh_id)  # Get the (x, y) coordinates
        print(f"Vehicle {veh_id}: Speed = {speed_kmh:.2f} km/h, Position = {position}")

    
if __name__ == "__main__":
    run_simulation()
