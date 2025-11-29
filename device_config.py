import random
from config import DEVICE_CONFIGS

used_devices = set()

def get_random_device_config():
    available_devices = [d for d in DEVICE_CONFIGS if d["platform"] not in used_devices]
    
    if not available_devices:
        used_devices.clear()
        available_devices = DEVICE_CONFIGS.copy()
        print("🔄 Все типы устройств использованы, начинаем заново")
    
    device = random.choice(available_devices)
    used_devices.add(device["platform"])
    return device

