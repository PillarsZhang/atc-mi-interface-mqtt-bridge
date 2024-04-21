$currentFolder = Split-Path -Path $PWD -Leaf
pyinstaller main.py --noconfirm --name $currentFolder --copy-metadata ha_mqtt_discoverable
