from aurorapy.client import AuroraError, AuroraSerialClient
import logging
from time import sleep
from functools import cached_property
from pprint import pprint
from influxdb import InfluxDBClient

class AuroraInterface:
    def __init__(
            self,
            serial_port: str = "/dev/ttyUSB1",
            address: int = 2,
            ):
        self.serial_port = serial_port
        self.address = address
        self.aurora_client = AuroraSerialClient(
                port=self.serial_port,
                address=self.address,
                )
        
    def connect(self):
        self.aurora_client.connect()
        logging.info(f"Aurora inverter {self.serial_number} connected")
    
    @cached_property
    def serial_number(self) -> str:
        return str(self.aurora_client.serial_number())
    
    def grid_frequency(self) -> float:
        return self.aurora_client.measure(4)
    
    def grid_voltage(self) -> float:
        return self.aurora_client.measure(1)
    
    def grid_voltage_average(self) -> float:
        return self.aurora_client.measure(32)
    
    def output_current(self) -> float:
        return self.aurora_client.measure(2)
    
    def output_power(self) -> float:
        return self.aurora_client.measure(3)
    
    def inverter_temperature(self) -> float:
        return self.aurora_client.measure(21)

    def booster_temperature(self) -> float:
        return self.aurora_client.measure(22)
    
    def power_peak(self) -> float:
        return self.aurora_client.measure(34)
    
    def power_peak_today(self) -> float:
        return self.aurora_client.measure(35)
    
    def input_1_voltage(self) -> float:
        return self.aurora_client.measure(23)

    def input_1_current(self) -> float:
        return self.aurora_client.measure(25)
    
    def input_2_voltage(self) -> float:
        return self.aurora_client.measure(26)
    
    def input_2_current(self) -> float:
        return self.aurora_client.measure(27)
    
    def input_current_total(self) -> float:
        return self.input_1_current() + self.input_2_current()
    
    def pv_energy_today(self) -> float:
        return self.aurora_client.cumulated_energy(period=0)
    1
    def pv_energy_week(self) -> float:
        return self.aurora_client.cumulated_energy(period=1)

    def pv_energy_month(self) -> float:
        return self.aurora_client.cumulated_energy(period=3)
    
    def pv_energy_year(self) -> float:
        return self.aurora_client.cumulated_energy(period=4)
    
    def pv_energy_total(self) -> float:
        return self.aurora_client.cumulated_energy(period=5)
    
    def pv_energy_since_reset(self) -> float:
        return self.aurora_client.cumulated_energy(period=6)
    
    def inverter_status(self) -> str:
        return self.aurora_client.state(state_type=2)

    def get_measurements(self) -> dict:
        measurements = {
            "PV_Energy_Today": self.pv_energy_today(),
            "PV_Energy_Total": self.pv_energy_total(),
            # "PV_Energy_Year": self.pv_energy_year(),
            # "PV_Energy_Month": self.pv_energy_month(),
            # "PV_Energy_Week": self.pv_energy_week(),
            "Inverter Status": self.inverter_status(),
            "PV_Power": self.output_power(),
            "PV_Voltage": self.grid_voltage(),
            # "PV_Power": self.output_power(),
            "Output_Watts": self.output_power(),
            "Output_Current": self.output_current(),
            }
        return measurements

if __name__ == "__main__":

    ports = ["/dev/ttyUSB2", "/dev/ttyUSB3"]
    interfaces = [AuroraInterface(serial_port=port, address=2) for port in ports]
    for interface in interfaces:
        interface.connect()

    db_client = InfluxDBClient(host="192.168.1.70", port=8086)
    db_client.switch_database("mydb")

    while True:
        for interface in interfaces:  
            measurements = interface.get_measurements()

            for key, value in measurements.items():
                # MEAS_NAME,sensor=SENSOR_NAME value=VALUE
                json_body = [
                    {
                        "measurement": key,
                        "tags": {
                            "sensor": interface.serial_number,
                            },
                        "fields": {
                            "value": value,
                            },
                        }
                    ]
                pprint(json_body)
                db_client.write_points(json_body)
        sleep(2)