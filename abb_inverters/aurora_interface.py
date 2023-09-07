from functools import cached_property
from time import sleep
import logging
from pprint import pprint
from pathlib import Path
from aurorapy import AuroraError, AuroraSerialClient, AuroraBaseClient
import serial
from influxdb import InfluxDBClient
from .secrets import influxdb_host, influxdb_port, influxdb_db, serial_port_1, serial_port_2, influxdb_user, influxdb_password
class AuroraInterface:
    def __init__(
            self,
            aurora_client: AuroraSerialClient,
            ):
        self.aurora_client = aurora_client

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


def get_aurora_clients(single_interface: bool = True) -> list[AuroraInterface]:
    ports = [str(port) for port in Path("/dev/").glob("ttyUSB*")]
    if single_interface:
        serial_interface = serial.Serial(
            port=ports[0],
            baudrate=19200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        serial_interface.open()
        interfaces = [
            AuroraInterface(serial_port=ports[0], address=2),
            AuroraInterface(serial_port=ports[0], address=3),
            ]
    else:
        interfaces = [
            AuroraSerialClient.from_connection_parameters(
                port=port,
                address=2,
                baudrate=19200,
                parity='N',
                stop_bits=1,
                data_bits=8,
                timeout=5,
                tries=3,
            ) for port in ports
        ]

    return interfaces

def read_and_write_to_db(interfaces: list[AuroraInterface], db_client: InfluxDBClient):
    while True:
        for interface in interfaces:  
            measurements = {}
            try:
                measurements = interface.get_measurements()
            except AuroraError as err:
                if "must connect client" in str(err):
                    interface.connect()
                    measurements = interface.get_measurements()
                elif "wrong CRC" in str(err):
                    sleep(0.5)
                    continue
                elif "Unkwnown transmission state" in str(err):
                    sleep(0.5)
                    continue
                else:
                    continue

            if measurements != {}:
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


if __name__ == "__main__":
    
    interfaces = get_aurora_clients(single_interface=True)

    for interface in interfaces:
        interface.connect()

    db_client = InfluxDBClient(
        host=influxdb_host, port=influxdb_port, username=influxdb_user, password=influxdb_password)
    db_client.switch_database(influxdb_db)

    read_and_write_to_db(interfaces, db_client)