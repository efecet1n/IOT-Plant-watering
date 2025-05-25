import sys
import utime
import uasyncio as asyncio
import machine
import network
import ntptime
import config
import blynk_mqtt
from demo import Device

BLYNK_FIRMWARE_VERSION = "PicoPlant"

# Check MQTT instance
if not hasattr(blynk_mqtt, 'mqtt') or blynk_mqtt.mqtt is None:
    print("FATAL ERROR: blynk_mqtt.py does not provide 'mqtt' instance!")
    sys.exit()

mqtt_client = blynk_mqtt.mqtt
plant_device = Device(mqtt_client)

def on_mqtt_message(topic_bytes, payload_bytes):
    # Handle MQTT message
    print("MQTT message callback triggered.")
    plant_device.blynk_process_mqtt_message(topic_bytes, payload_bytes)

def on_mqtt_connect():
    # Handle MQTT connection
    plant_device.blynk_connected_callback()

def on_mqtt_disconnect():
    # Handle MQTT disconnection
    if hasattr(plant_device, 'blynk_mqtt_disconnected_callback'):
        plant_device.blynk_mqtt_disconnected_callback()

# Set MQTT callbacks
blynk_mqtt.on_message = on_mqtt_message
blynk_mqtt.on_connected = on_mqtt_connect
if hasattr(blynk_mqtt, 'on_disconnected'):
    blynk_mqtt.on_disconnected = on_mqtt_disconnect
if hasattr(blynk_mqtt, 'firmware_version'):
    blynk_mqtt.firmware_version = BLYNK_FIRMWARE_VERSION

def setup_network_and_time():
    # Connect to WiFi and sync time
    sta_if = network.WLAN(network.STA_IF)
    wifi_conn = sta_if.isconnected()
    if not wifi_conn:
        sta_if.active(True)
        try:
            sta_if.disconnect()
            utime.sleep_ms(200)
        except OSError:
            pass
        sta_if.connect(config.WIFI_SSID, config.WIFI_PASS)
        t = 25
        while not sta_if.isconnected() and t > 0:
            utime.sleep(1)
            t -= 1
    if sta_if.isconnected():
        if not wifi_conn:
            print(f"WiFi connected! IP: {sta_if.ifconfig()[0]}")
        ntp_ok = False
        for _ in range(3):
            try:
                ntptime.timeout = 7
                ntptime.settime()
                utc_dt = machine.RTC().datetime()
                utc_ts = utime.mktime((utc_dt[0], utc_dt[1], utc_dt[2], utc_dt[4], utc_dt[5], utc_dt[6], utc_dt[3], 0))
                local_ts = utc_ts + (3 * 3600)
                y, m, d, hr, mi, s, wd, _ = utime.localtime(local_ts)
                machine.RTC().datetime((y, m, d, wd, hr, mi, s, 0))
                dt_local = machine.RTC().datetime()
                print(f"RTC local time: {dt_local[2]:02d}/{dt_local[1]:02d} {dt_local[4]:02d}:{dt_local[5]:02d}")
                ntp_ok = True
                break
            except Exception as e:
                if _ == 2:
                    print(f"NTP error: {e}")
                if _ < 2:
                    utime.sleep(3)
        if not ntp_ok:
            print("NTP sync failed.")
        return True
    else:
        print("WiFi failed!")
        return False

async def physical_button_check_task():
    # Check physical button
    button_pin = plant_device.power_button
    while True:
        if button_pin.value() == 0:
            if plant_device.toggle_system_power():
                await asyncio.sleep_ms(plant_device.button_debounce_duration_ms + 100)
        await asyncio.sleep_ms(50)

async def mqtt_check_task():
    # Check MQTT messages
    while True:
        try:
            if mqtt_client and hasattr(mqtt_client, 'sock') and mqtt_client.sock is not None:
                mqtt_client.check_msg()
            else:
                print("MQTT not connected, skipping check.")
        except Exception as e:
            print(f"MQTT check error: {e}")
            await asyncio.sleep(1)
        await asyncio.sleep_ms(100)

async def app_task():
    # Main application loop
    interval_s = 30  # 30s for sensor reading
    http_interval_s = config.HTTP_BLYNK_UPDATE_INTERVAL_S
    last_http_update_s = utime.time() - http_interval_s

    while True:
        current_s = utime.time()
        if plant_device.system_active:
            try:
                await plant_device.read_all_sensors_sequentially()
                if (current_s - last_http_update_s) >= http_interval_s:
                    plant_device.update_blynk_http()
                    last_http_update_s = current_s
                plant_device.update_blynk_mqtt_pump_status()
                await plant_device.run_smart_plant_logic()
                plant_device.print_sensor_data_to_terminal()
            except Exception as e:
                print(f"App task error: {e}")
        await asyncio.sleep(interval_s)

async def start_system():
    # Start system tasks
    try:
        import urequests
    except ImportError:
        print("ERROR: 'urequests' missing!")
        return

    if sys.platform != "linux":
        if not setup_network_and_time():
            print("CRITICAL: No WiFi. System will wait for power button.")
            return

    # System starts in OFF state, waiting for button press
    plant_device.system_active = False
    print("System ready. Press GP5 to activate.")

    loop = asyncio.get_event_loop()
    loop.create_task(blynk_mqtt.task())
    loop.create_task(mqtt_check_task())
    loop.create_task(app_task())
    loop.create_task(physical_button_check_task())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        if hasattr(plant_device.mqtt, 'sock') and plant_device.mqtt.sock:
            try:
                plant_device.mqtt.disconnect()
                print("MQTT closed.")
            except:
                pass
        if hasattr(plant_device, 'pump_pin'):
            plant_device.pump_pin.off()
            print("Pump off.")
        loop.close()
        print("App terminated.")

if __name__ == "__main__":
    asyncio.run(start_system())
