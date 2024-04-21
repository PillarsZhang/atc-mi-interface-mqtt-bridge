# ATC MI Interface MQTT Bridge

This is a Python-based project that scans ATC Mi devices and publishes the data to an MQTT server.

## Installation

First, you need to install Python and pip. Then, you can install the dependencies of the project with the following command:

```bash
pip install -r requirements.txt
```

## Usage

You can run the project with the following command:

```bash
python main.py
```

## Configuration

You can configure your devices and MQTT server in the `config.yaml` file. An example configuration can be found in the `config.example.yaml` file.

```yaml
mqtt:
    host: ...
    port: ...
    username: ...
    password: ...
devices:
    - id: &id_ATC_ABCDEF atc_abcdef
      mac_address: &mac_address_ATC_ABCDEF A4C138ABCDEF
      bindkey: ...
      device_info:
          # https://www.mi.com/pl/product/mi-temperature-and-humidity-monitor-2/
          name: Mi Temperature and Humidity Monitor 2 ATC_ABCDEF
          model: LYWSD03MMC
          manufacturer: Xiaomi
          sw_version: V4.7
          hw_version: B1.5
          identifiers: [*mac_address_ATC_ABCDEF]
          configuration_url: https://pvvx.github.io/ATC_MiThermometer/TelinkMiFlasher.html
      sensor:
          temperature:
              name: Temperature
              unit_of_measurement: "°C"
              state_class: measurement
              device_class: temperature
          humidity:
              name: Humidity
              unit_of_measurement: "%"
              state_class: measurement
              device_class: humidity
          battery_level:
              name: Battery
              unit_of_measurement: "%"
              state_class: measurement
              device_class: battery
          battery_v:
              name: Battery Voltage
              unit_of_measurement: "V"
              state_class: measurement
              device_class: voltage
          signal_strength:
              name: Signal Strength
              unit_of_measurement: "dBm"
              state_class: measurement
              device_class: signal_strength
```

## Building

You can build the project with the following command:

```powershell
# .\build.ps1
$currentFolder = Split-Path -Path $PWD -Leaf
pyinstaller main.py --noconfirm --name $currentFolder --copy-metadata ha_mqtt_discoverable
```
