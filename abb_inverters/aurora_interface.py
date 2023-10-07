from functools import cached_property
from time import sleep
import logging
from pprint import pprint
from pathlib import Path
from aurorapy import AuroraError, AuroraSerialClient, AuroraBaseClient
import serial
from serial.tools.list_ports import comports
# from influxdb import InfluxDBClient
from influxdb_client import InfluxDBClient, Point, WritePrecision, WriteApi
from influxdb_client.client.write_api import SYNCHRONOUS

import secrets
class AuroraInterface:
    def __init__(
            self,
            aurora_client: AuroraSerialClient,
            ):
        self.aurora_client = aurora_client

    def connect(self):
        self.aurora_client.connect()
        print(f"Aurora inverter {self.serial_number} connected")
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
    # ports = [str(port) for port in Path("/dev/").glob("ttyUSB*")]

    com_ports = [comport for comport in comports() if comport.vid == 6790]

    if single_interface:
        port = [port for port in com_ports if port.location == "1-1.2"]
        serial_interface = serial.Serial(
            port=port[0].device,
            baudrate=19200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
        serial_clients = [
            AuroraSerialClient(serial_line=serial_interface, address=2),
            AuroraSerialClient(serial_line=serial_interface, address=3)
            ]
        interfaces = [
            AuroraInterface(aurora_client=client) for client in serial_clients
            ]
        
    else:
        interfaces = [
            AuroraSerialClient.from_connection_parameters(
                port=com_port.device,
                address=2,
                baudrate=19200,
                parity='N',
                stop_bits=1,
                data_bits=8,
                timeout=5,
                tries=3,
            ) for com_port in com_ports
        ]

    return interfaces

def read_and_write_to_db(interfaces: list[AuroraInterface], db_client_api: WriteApi):
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
                    point = (
                        Point(str(interface.serial_number))
                        .field(key, value)
                    )
                    db_client_api.write(
                        bucket=secrets.influxdb_bucket,
                        org=secrets.influxdb_org,
                        record=point)
                sleep(2)
def main_loop():
    single_interface: bool = True
    interfaces = get_aurora_clients(single_interface=single_interface)
    print(f"Found {len(interfaces)} Aurora inverters")
    print(interfaces)
    connect(interfaces, single_interface=single_interface)

    write_client = InfluxDBClient(
        url=secrets.influxdb_url,
        token=secrets.influxdb_token,
        org=secrets.influxdb_org,
        )
    write_api = write_client.write_api(write_options=SYNCHRONOUS)
    read_and_write_to_db(interfaces, write_client)


def connect(interfaces: list[AuroraInterface], single_interface: bool = True):
    try:
        if single_interface:
            interfaces[0].connect()
        else:
            for interface in interfaces:
                interface.connect()
    except AuroraError as err:
        sleep(1)
        connect(interfaces, single_interface=single_interface)
    return


if __name__ == "__main__":
    while True:
        try:
            main_loop()
        except:
            pass
