import os
from pathlib import Path
import sys
import yaml
import fire
from loguru import logger
import asyncio
from bleak import BleakScanner
from atc_mi_interface import general_format, atc_mi_advertising_format
from ha_mqtt_discoverable import Settings, DeviceInfo
from ha_mqtt_discoverable.sensors import Sensor, SensorInfo


def mac_bytes_to_str(mac_bytes: bytes, split_char: str = ":") -> str:
    return split_char.join(f"{byte:02X}" for byte in mac_bytes)


def mac_str_to_bytes(mac_str: str, split_char: str = ":") -> bytes:
    return bytes.fromhex(mac_str.replace(split_char, ""))


async def task_wrapper(task_func, *args, **kwargs):
    task_name = task_func.__name__
    while True:
        try:
            logger.info(f"Starting task: {task_name}, args: {args}, kwargs: {kwargs}")
            await task_func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Task {task_name}, args: {args}, kwargs: {kwargs} "
                f"failed with error: {e}. Restarting..."
            )
            await asyncio.sleep(10)


async def ble_scanner(
    bindkey: dict[bytes, bytes], sensorkey: dict[bytes, tuple], queue: asyncio.Queue
):
    async with BleakScanner(scanning_mode="passive") as scanner:
        count = 0
        logger.info("Scanning for ATC Mi devices...")
        async for device, advertisement_data in scanner.advertisement_data():
            mac_address = mac_str_to_bytes(device.address)
            if mac_address not in bindkey:
                continue
            format_label, adv_data = atc_mi_advertising_format(advertisement_data)
            if not adv_data:
                continue
            logger.debug(
                f"{count}. MAC: {device.address}, advertisement_data: {advertisement_data}"
            )
            atc_mi_data = general_format.parse(
                adv_data,
                mac_address=mac_address,
                bindkey=bindkey[mac_address] if mac_address in bindkey else None,
            )
            logger.debug(
                f"{count}. MAC: {device.address}, {format_label} advertisement:\n{atc_mi_data}\n"
                f"RSSI: {advertisement_data.rssi}"
            )

            data = dict(signal_strength=(advertisement_data.rssi, "dBm"))
            for key in sensorkey[mac_address]:
                if value := atc_mi_data.search_all(f"^{key}"):
                    unit = atc_mi_data.search_all(f"^{key}_unit")
                    data[key] = value[0], (unit[0] if unit else None)
            await queue.put((count, mac_address, data))
            count += 1


async def log_data(queue: asyncio.Queue):
    while True:
        index, mac_address, data = await queue.get()
        logger.info(f"{index=}, {mac_bytes_to_str(mac_address)=}, {data=}")
        queue.task_done()


async def mqtt_publisher(queue: asyncio.Queue, mqtt_config: dict, devices_config: dict):
    mqtt_settings = Settings.MQTT(**mqtt_config)
    device_dic = dict()

    for c in devices_config:
        device_info = DeviceInfo(**c["device_info"])
        device_sensor = dict()
        for key, value in c["sensor"].items():
            sensor_info = SensorInfo(
                **value,
                unique_id=f"{c['id']}_{key}",
                device=device_info,
            )
            settings = Settings(mqtt=mqtt_settings, entity=sensor_info)
            sensor = Sensor(settings)
            device_sensor[key] = sensor
            logger.info(f"Config sensor: {sensor.config_topic}")
        device_dic[mac_str_to_bytes(c["mac_address"])] = dict(
            info=device_info, sensor=device_sensor, config=c
        )

    num_item_ignore = 0
    try:
        while True:
            queue.get_nowait()
            num_item_ignore += 1
    except asyncio.QueueEmpty:
        logger.info(f"Ignore {num_item_ignore} items in queue")

    while True:
        index, mac_address, data = await queue.get()
        logger.debug(f"{index=}, {mac_bytes_to_str(mac_address)=}, {data=}")
        # Log example:
        # index=1, mac_bytes_to_str(mac_address)='A4:C1:38:7A:A5:7E',
        # data={'temperature': (29.93, '°C'), 'humidity': (37.44, '%'), 'battery_level': (100, '%')}

        # https://github.com/unixorn/ha-mqtt-discoverable/issues/84#issuecomment-1509213814
        for key, (value, unit) in data.items():
            sensor: Sensor = device_dic[mac_address]["sensor"][key]
            unit_of_measurement = device_dic[mac_address]["config"]["sensor"][key][
                "unit_of_measurement"
            ]
            if unit == unit_of_measurement:
                sensor.set_state(value)
                logger.debug(f"Set state: {sensor.state_topic=} as {value} {unit}")
            else:
                logger.error(f"Unit mismatch: {key=}, {value=}, {unit=}, {unit_of_measurement=}")


def main(
    work_dir: str = None,
    bridge: bool = False,
    config: str = "./config.yaml",
    log_level: str = "INFO",
    log_file: str = "./logs/{time}.log",
):
    if work_dir:
        os.chdir(work_dir)

    logger.remove()
    logger.add(sys.stdout, level=log_level)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=log_level, mode="w")

    with open(config, "r", encoding="utf-8") as f:
        config_dic = yaml.safe_load(f)
    bindkey = {
        mac_str_to_bytes(item["mac_address"]): bytes.fromhex(item["bindkey"])
        for item in config_dic["devices"]
    }
    sensorkey = {
        mac_str_to_bytes(item["mac_address"]): tuple(item["sensor"].keys())
        for item in config_dic["devices"]
    }

    queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    if not bridge:
        loop.run_until_complete(
            asyncio.gather(
                task_wrapper(ble_scanner, bindkey, sensorkey, queue),
                task_wrapper(log_data, queue),
            )
        )
    else:
        loop.run_until_complete(
            asyncio.gather(
                task_wrapper(ble_scanner, bindkey, sensorkey, queue),
                task_wrapper(mqtt_publisher, queue, config_dic["mqtt"], config_dic["devices"]),
            )
        )


if __name__ == "__main__":
    fire.Fire(main)
