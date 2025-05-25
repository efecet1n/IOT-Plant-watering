import machine
import dht
import config
import urequests
import gc
import utime
import uasyncio as asyncio

class Device:
    def __init__(self, mqtt_client):
        self.mqtt = mqtt_client
        self.loop = asyncio.get_event_loop()

        # Add last sensor update time tracking
        self.last_sensor_update_s = 0

        # Pin assignments
        self.PIN_SOIL_MOISTURE_ADC = config.PIN_SOIL_MOISTURE_ADC
        self.PIN_SOIL_MOISTURE_VCC = config.PIN_SOIL_MOISTURE_VCC
        self.PIN_WATER_LEVEL_ADC = config.PIN_WATER_LEVEL_ADC
        self.PIN_LDR_ADC = config.PIN_LDR_ADC
        self.PIN_DHT11_DATA = config.PIN_DHT11_DATA
        self.PIN_PUMP_CONTROL = config.PIN_PUMP_CONTROL
        self.PIN_BUZZER = config.PIN_BUZZER
        self.PIN_SYSTEM_POWER_BUTTON = config.PIN_SYSTEM_POWER_BUTTON

        # Virtual pins
        self.VPIN_SOIL_MOISTURE_PERCENT = config.VPIN_SOIL_MOISTURE_PERCENT
        self.VPIN_LIGHT_LEVEL_PERCENT = config.VPIN_LIGHT_LEVEL_PERCENT
        self.VPIN_TEMPERATURE = config.VPIN_TEMPERATURE
        self.VPIN_HUMIDITY = config.VPIN_HUMIDITY
        self.VPIN_PUMP_SWITCH = config.VPIN_PUMP_SWITCH
        self.VPIN_WATER_LEVEL_PERCENT = config.VPIN_WATER_LEVEL_PERCENT
        self.VPIN_SYSTEM_MESSAGE = config.VPIN_SYSTEM_MESSAGE
        self.VPIN_LAST_WATERING_TIME = config.VPIN_LAST_WATERING_TIME
        self.VPIN_WATERING_LOCKOUT_HOURS = config.VPIN_WATERING_LOCKOUT_HOURS
        self.VPIN_MANUAL_WATERING_DURATION_S = config.VPIN_MANUAL_WATERING_DURATION_S
        self.VPIN_AUTO_WATERING_DURATION_S = config.VPIN_AUTO_WATERING_DURATION_S
        self.VPIN_SOIL_MOISTURE_THRESHOLD = config.VPIN_SOIL_MOISTURE_THRESHOLD

        # Calibration
        self.CAL_SOIL_ADC_DRY = config.CAL_SOIL_ADC_DRY
        self.CAL_SOIL_ADC_WET = config.CAL_SOIL_ADC_WET
        self.CAL_WATER_ADC_EMPTY = config.CAL_WATER_ADC_EMPTY
        self.CAL_WATER_ADC_FULL = config.CAL_WATER_ADC_FULL
        self.WATER_ADC_LOW_THRESHOLD_VALUE = config.WATER_ADC_LOW_THRESHOLD_VALUE
        self.CAL_LDR_ADC_BRIGHT = config.CAL_LDR_ADC_BRIGHT
        self.CAL_LDR_ADC_DARK = config.CAL_LDR_ADC_DARK

        # Thresholds and settings
        self.THRESHOLD_SOIL_MOISTURE_WATERING_DEFAULT = config.DEFAULT_SOIL_MOISTURE_WATERING_THRESHOLD
        self.THRESHOLD_LIGHT_INSUFFICIENT = config.THRESHOLD_LIGHT_INSUFFICIENT_PERCENT
        self.LDR_DAYTIME_MIN_LIGHT_PERCENT = config.LDR_DAYTIME_MIN_LIGHT_PERCENT
        self.WATERING_ALLOWED_HOUR_START = config.WATERING_ALLOWED_HOUR_START
        self.WATERING_ALLOWED_HOUR_END = config.WATERING_ALLOWED_HOUR_END
        self.MIN_SECONDS_BETWEEN_WATERING_DEFAULT = config.DEFAULT_MIN_SECONDS_BETWEEN_WATERING
        self.PUMP_RUN_DURATION_AUTO_DEFAULT_S = config.DEFAULT_PUMP_RUN_DURATION_AUTO_S
        self.LDR_ADC_MAX_DARKNESS_FOR_WATERING = config.LDR_ADC_MAX_DARKNESS_FOR_WATERING
        self.SENSOR_POWER_ON_DELAY_MS = config.SENSOR_POWER_ON_DELAY_MS
        self.DHT_READ_INTERVAL_MS = config.DHT_READ_INTERVAL_MS
        self.LOW_WATER_ALARM_INTERVAL_S = config.LOW_WATER_ALARM_INTERVAL_S
        self.DEVICE_ID = config.DEVICE_ID

        # Hardware initialization
        self.soil_adc = machine.ADC(self.PIN_SOIL_MOISTURE_ADC)
        self.soil_vcc = machine.Pin(self.PIN_SOIL_MOISTURE_VCC, machine.Pin.OUT, value=0)
        self.water_adc = machine.ADC(self.PIN_WATER_LEVEL_ADC)
        self.ldr_adc = machine.ADC(self.PIN_LDR_ADC)
        self.dht_sensor = dht.DHT11(machine.Pin(self.PIN_DHT11_DATA))
        self.pump_pin = machine.Pin(self.PIN_PUMP_CONTROL, machine.Pin.OUT, value=0)
        self.buzzer_pwm = machine.PWM(machine.Pin(self.PIN_BUZZER))
        self.buzzer_pwm.duty_u16(0)
        self.power_button = machine.Pin(self.PIN_SYSTEM_POWER_BUTTON, machine.Pin.IN, machine.Pin.PULL_UP)

        # Blynk URL
        self.blynk_url = f"https://{config.BLYNK_MQTT_BROKER}/external/api/batch/update?token={config.BLYNK_AUTH_TOKEN}"

        # State variables
        self.last_dht_read_ms = 0
        self.cached_temp, self.cached_hum = None, None
        self.last_watering_s = 0
        self.current_soil_percent, self.current_water_percent = 0, 0
        self.current_light_percent, self.current_raw_ldr_adc = 0, 0
        self.current_raw_soil_adc = 0
        self.current_raw_water_adc = 0
        self.rtc = machine.RTC()
        self.last_system_message_s = 0  # Track last V6 message time

        # Config variables
        self.min_seconds_between_watering_config = self.MIN_SECONDS_BETWEEN_WATERING_DEFAULT
        self.pump_run_duration_auto_s = self.PUMP_RUN_DURATION_AUTO_DEFAULT_S
        self.pump_run_duration_manual_s = 10
        self.soil_watering_threshold_config = self.THRESHOLD_SOIL_MOISTURE_WATERING_DEFAULT

        # Alarm and system state
        self.low_water_alarm_active = False
        self.last_low_water_alarm_played_s = 0
        self.system_active = False
        self.last_button_press_time_ms = 0
        self.button_debounce_duration_ms = 250

        print("Device initialized.")

    async def _play_tone_async(self, frequency, duration_ms, duty_cycle=32768):
        if frequency <= 0:
            return
        try:
            self.buzzer_pwm.freq(frequency)
            self.buzzer_pwm.duty_u16(duty_cycle)
            await asyncio.sleep_ms(duration_ms)
        except Exception as e:
            pass
        finally:
            self.buzzer_pwm.duty_u16(0)

    async def test_buzzer(self):
        # Test buzzer with a simple tone
        print("Testing buzzer...")
        await self._play_tone_async(1000, 500)  # 1000Hz, 500ms

    async def play_sound_sequence_async(self, tones_sequence, inter_tone_delay_ms=50):
        # Play tone sequence
        print(f"Playing sound sequence: {tones_sequence}")
        try:
            for freq, duration in tones_sequence:
                await self._play_tone_async(freq, duration)
                if inter_tone_delay_ms > 0:
                    await asyncio.sleep_ms(inter_tone_delay_ms)
        except Exception as e:
            print(f"Sound sequence error: {e}")
        finally:
            self.buzzer_pwm.duty_u16(0)
            print("Sound sequence stopped.")

    def play_startup_sound(self):
        # Play three-note startup sequence
        startup_sequence = [(523, 100), (659, 100), (784, 150)]  # C5, E5, G5
        self.loop.create_task(self.play_sound_sequence_async(startup_sequence, 100))

    def play_shutdown_sound(self):
        # Play three-note shutdown sequence
        shutdown_sequence = [(784, 150), (659, 100), (523, 100)]  # G5, E5, C5
        self.loop.create_task(self.play_sound_sequence_async(shutdown_sequence, 100))

    def play_watering_action_sound(self, start=True):
        # Sadece manuel sulama için ses
        if not start:  # Sadece bitişte ses çal
            self.loop.create_task(self._play_tone_async(600, 100))

    def play_setting_change_sound(self):
        # Ayar değişikliği sesi
        self.loop.create_task(self._play_tone_async(1200, 50))

    async def low_water_alarm_task(self):
        # Low water alarm
        self.low_water_alarm_active = True
        print("Starting low water alarm task...")
        while self.low_water_alarm_active and self.system_active:
            if self.current_raw_water_adc < self.WATER_ADC_LOW_THRESHOLD_VALUE and self.current_raw_water_adc != 0:
                if hasattr(config, 'TONE_LOW_WATER_ALARM'):
                    print(f"Playing low water alarm: {config.TONE_LOW_WATER_ALARM}")
                    await self._play_tone_async(config.TONE_LOW_WATER_ALARM[0], config.TONE_LOW_WATER_ALARM[1])
            else:
                self.low_water_alarm_active = False
                break
            await asyncio.sleep(self.LOW_WATER_ALARM_INTERVAL_S)
        self.buzzer_pwm.duty_u16(0)
        print("Low water alarm task stopped.")

    def _read_adc_avg_sync(self, adc_obj, samples=10, delay_ms=5):
        # Read ADC average
        total = 0
        count = 0
        for _ in range(samples):
            try:
                total += adc_obj.read_u16()
                count += 1
                if delay_ms > 0:
                    utime.sleep_ms(delay_ms)
            except OSError:
                pass
        return total // count if count > 0 else 32767

    def _map_value(self, x, in_min, in_max, out_min, out_max, clamp=True):
        # Map value
        if clamp:
            phys_min = min(in_min, in_max)
            phys_max = max(in_min, in_max)
            x = max(phys_min, min(x, phys_max))
        if (in_max - in_min) == 0:
            return out_min
        return int(((x - in_min) * (out_max - out_min)) / (in_max - in_min) + out_min)

    def read_soil_percentage(self):
        # Read soil moisture
        self.soil_vcc.high()
        utime.sleep_ms(self.SENSOR_POWER_ON_DELAY_MS)
        raw = self._read_adc_avg_sync(self.soil_adc, samples=15)
        self.soil_vcc.low()
        self.current_raw_soil_adc = raw
        self.current_soil_percent = self._map_value(raw, self.CAL_SOIL_ADC_DRY, self.CAL_SOIL_ADC_WET, 0, 100)
        return self.current_soil_percent

    def read_light_percentage(self):
        # Read light level
        raw = self._read_adc_avg_sync(self.ldr_adc, samples=5)
        self.current_raw_ldr_adc = raw
        self.current_light_percent = self._map_value(raw, self.CAL_LDR_ADC_BRIGHT, self.CAL_LDR_ADC_DARK, 100, 10)
        return self.current_light_percent

    def read_temperature_humidity(self):
        # Read temperature and humidity
        if utime.ticks_diff(utime.ticks_ms(), self.last_dht_read_ms) > self.DHT_READ_INTERVAL_MS or self.cached_temp is None:
            try:
                self.dht_sensor.measure()
                temp = self.dht_sensor.temperature()
                hum = self.dht_sensor.humidity()
                self.cached_temp = temp if -20 <= temp <= 60 else None
                self.cached_hum = hum if 0 <= hum <= 100 else None
                self.last_dht_read_ms = utime.ticks_ms()
            except Exception:
                self.cached_temp = None
                self.cached_hum = None
        return self.cached_temp, self.cached_hum

    def read_water_level_percentage(self):
        # Read water level
        raw = self._read_adc_avg_sync(self.water_adc, samples=15)
        self.current_raw_water_adc = raw
        self.current_water_percent = self._map_value(raw, self.CAL_WATER_ADC_EMPTY, self.CAL_WATER_ADC_FULL, 0, 100)
        return self.current_water_percent

    async def read_all_sensors_sequentially(self):
        # Read all sensors
        if not self.system_active:
            return
        self.read_soil_percentage()
        await asyncio.sleep_ms(50)
        self.read_water_level_percentage()
        await asyncio.sleep_ms(50)
        self.read_light_percentage()
        await asyncio.sleep_ms(50)
        self.read_temperature_humidity()

    def update_blynk_http(self):
        # Update Blynk via HTTP
        if not self.system_active:
            return
        payload = {}
        if self.current_soil_percent is not None:
            payload[f"V{config.VPIN_SOIL_MOISTURE_PERCENT}"] = self.current_soil_percent
        if self.current_light_percent is not None:
            payload[f"V{config.VPIN_LIGHT_LEVEL_PERCENT}"] = self.current_light_percent
        if self.cached_temp is not None:
            payload[f"V{config.VPIN_TEMPERATURE}"] = self.cached_temp
        if self.cached_hum is not None:
            payload[f"V{config.VPIN_HUMIDITY}"] = self.cached_hum
        if self.current_water_percent is not None:
            payload[f"V{config.VPIN_WATER_LEVEL_PERCENT}"] = self.current_water_percent
        if self.last_watering_s > 0:
            elapsed_seconds = utime.time() - self.last_watering_s
            elapsed_hours = elapsed_seconds // 3600
            elapsed_minutes = (elapsed_seconds % 3600) // 60
            payload[f"V{config.VPIN_LAST_WATERING_TIME}"] = f"{elapsed_hours}h {elapsed_minutes}m"
        else:
            payload[f"V{config.VPIN_LAST_WATERING_TIME}"] = "Never"
        payload[f"V{config.VPIN_WATERING_LOCKOUT_HOURS}"] = self.min_seconds_between_watering_config // 3600
        payload[f"V{config.VPIN_MANUAL_WATERING_DURATION_S}"] = self.pump_run_duration_manual_s
        payload[f"V{config.VPIN_AUTO_WATERING_DURATION_S}"] = self.pump_run_duration_auto_s
        payload[f"V{config.VPIN_SOIL_MOISTURE_THRESHOLD}"] = self.soil_watering_threshold_config

        if payload:
            try:
                query = "&".join([f"{k}={v}" for k, v in payload.items()])
                url = f"{self.blynk_url}&{query}"
                resp = urequests.get(url, timeout=7)
                resp.close()
                gc.collect()
                self.last_sensor_update_s = utime.time()  # Update last sensor update time
            except Exception as e:
                print(f"HTTP Error: {e}")
                self.send_system_message_mqtt(f"HTTP Error: {e}")

    def _is_mqtt_ready(self):
        # Check MQTT readiness
        ready = self.mqtt and hasattr(self.mqtt, 'publish') and hasattr(self.mqtt, 'sock') and self.mqtt.sock is not None
        print(f"MQTT ready check: {ready}")
        return ready

    async def wait_for_mqtt(self):
        # Wait for MQTT to be ready
        for _ in range(10):
            if self._is_mqtt_ready():
                print("MQTT connection ready.")
                return True
            print("Waiting for MQTT connection...")
            await asyncio.sleep(1)
        print("MQTT connection timeout.")
        return False

    def update_blynk_mqtt_pump_status(self):
        # Update pump status instantly (V4)
        if not self.system_active and self.pump_pin.value() == 1:
            self.pump_pin.off()
        if self._is_mqtt_ready():
            try:
                topic = f"ds/{self.DEVICE_ID}/dp/V{self.VPIN_PUMP_SWITCH}"
                value = str(self.pump_pin.value())
                print(f"Publishing pump status: topic={topic}, value={value}")
                self.mqtt.publish(topic.encode('utf-8'), value.encode('utf-8'), qos=0)
            except Exception as e:
                print(f"MQTT Pump Error: {e}")
                self.send_system_message_mqtt(f"MQTT Pump Error: {e}")

    async def send_system_message_mqtt_async(self, message, force=False):
        if not await self.wait_for_mqtt():
            return
        now_s = utime.time()
        if force or (now_s - self.last_system_message_s >= 3600):  # 1 saatte bir normal mesaj
            try:
                now_dt = self.rtc.datetime()
                timestamp = f"{now_dt[4]:02d}:{now_dt[5]:02d}> "
                full_message = timestamp + str(message)[:64]
                topic = f"ds/{self.DEVICE_ID}/dp/V{self.VPIN_SYSTEM_MESSAGE}"
                print(f"Sending to V6: {full_message}")
                self.mqtt.publish(topic.encode('utf-8'), full_message.encode('utf-8'), qos=1)
                self.last_system_message_s = now_s
            except Exception as e:
                print(f"MQTT Error: {e}")

    def send_blynk_value_mqtt(self, vpin, value):
        # Send value to Blynk
        if self._is_mqtt_ready():
            try:
                topic = f"ds/{self.DEVICE_ID}/dp/V{vpin}"
                print(f"Sending MQTT: topic={topic}, value={value}")
                self.mqtt.publish(topic.encode('utf-8'), str(value).encode('utf-8'), qos=0)
            except Exception as e:
                print(f"MQTT V{vpin} Send Error: {e}")
                self.send_system_message_mqtt(f"MQTT V{vpin} Send Error: {e}")

    def send_system_message_mqtt(self, message, force=False):
        # Send system message to V6 (synchronous wrapper)
        if self._is_mqtt_ready():
            self.loop.create_task(self.send_system_message_mqtt_async(message, force))

    def _is_daytime(self):
        # Check if daytime
        return self.current_light_percent >= self.LDR_DAYTIME_MIN_LIGHT_PERCENT

    def _is_efficient_time_for_watering(self):
        # Check watering time
        hour = self.rtc.datetime()[4]
        return self.WATERING_ALLOWED_HOUR_START <= hour < self.WATERING_ALLOWED_HOUR_END

    async def run_smart_plant_logic(self):
        if not self.system_active:
            return

        messages = []
        now_s = utime.time()

        # Light check
        if self._is_daytime() and self.current_light_percent < self.THRESHOLD_LIGHT_INSUFFICIENT:
            messages.append("LOW LIGHT")

        # Water level check
        if self.current_raw_water_adc < self.WATER_ADC_LOW_THRESHOLD_VALUE and self.current_raw_water_adc != 0:
            messages.append("LOW WATER")
            if (not self.low_water_alarm_active and
                now_s - self.last_low_water_alarm_played_s > self.LOW_WATER_ALARM_INTERVAL_S * 3):
                self.loop.create_task(self.low_water_alarm_task())
                self.last_low_water_alarm_played_s = now_s
        elif self.low_water_alarm_active and self.current_raw_water_adc >= self.WATER_ADC_LOW_THRESHOLD_VALUE:
            self.low_water_alarm_active = False

        # Soil moisture check and watering logic
        if self.current_soil_percent < self.soil_watering_threshold_config:
            if self.pump_pin.value() == 1:
                pass
            elif self.current_water_percent < 20:
                messages.append("NO WATER")
            elif not self._is_efficient_time_for_watering():
                messages.append("NIGHT")
            elif (now_s - self.last_watering_s) < self.min_seconds_between_watering_config:
                remaining_time = self.min_seconds_between_watering_config - (now_s - self.last_watering_s)
                messages.append(f"LOCK {remaining_time//3600}h")
            elif self.current_raw_ldr_adc >= self.LDR_ADC_MAX_DARKNESS_FOR_WATERING:
                messages.append("DARK")
            else:
                messages.append("AUTO")
                self.play_watering_action_sound(start=True)
                self.pump_pin.on()
                self.update_blynk_mqtt_pump_status()
                await asyncio.sleep(self.pump_run_duration_auto_s)
                self.pump_pin.off()
                self.play_watering_action_sound(start=False)
                self.update_blynk_mqtt_pump_status()
                self.last_watering_s = now_s

    def blynk_connected_callback(self):
        print("MQTT Connected")
        if self._is_mqtt_ready():
            try:
                self.update_blynk_mqtt_pump_status()
                self.send_blynk_value_mqtt(self.VPIN_WATERING_LOCKOUT_HOURS, self.min_seconds_between_watering_config // 3600)
                self.send_blynk_value_mqtt(self.VPIN_MANUAL_WATERING_DURATION_S, self.pump_run_duration_manual_s)
                self.send_blynk_value_mqtt(self.VPIN_AUTO_WATERING_DURATION_S, self.pump_run_duration_auto_s)
                self.send_blynk_value_mqtt(self.VPIN_SOIL_MOISTURE_THRESHOLD, self.soil_watering_threshold_config)
            except Exception as e:
                print(f"MQTT Error: {e}")

    def blynk_process_mqtt_message(self, topic_bytes, payload_bytes):
        topic = topic_bytes.decode('utf-8')
        payload = payload_bytes.decode('utf-8')
        print(f"Received MQTT message: topic={topic}, payload={payload}")

        # Topic mapping
        topic_mapping = {
            "downlink/ds/Auto Watering Duration": self._handle_auto_duration,
            "downlink/ds/Manual Watering Duration": self._handle_manual_duration,
            "downlink/ds/Soil Moisture Threshold": self._handle_soil_threshold,
            "downlink/ds/Watering Lockout": self._handle_lockout,
            "downlink/ds/Water Pump Manual Control": self._handle_pump_control
        }

        handler = topic_mapping.get(topic)
        if handler:
            handler(payload)
        else:
            print(f"Unknown MQTT topic: {topic}")
            self.send_system_message_mqtt(f"Unknown MQTT topic: {topic}")

    def _handle_pump_control(self, payload):
        # Handle pump control from Blynk
        try:
            if payload == "1":
                self.pump_pin.on()
                self.loop.create_task(self._play_tone_async(659, 300))  # Play notification sound when pump is turned on
                print("Pump turned ON via Blynk")
            else:
                self.pump_pin.off()
                self.loop.create_task(self._play_tone_async(523, 300))  # Play notification sound when pump is turned off
                print("Pump turned OFF via Blynk")
        except Exception as e:
            print(f"Pump control error: {e}")

    def _handle_lockout(self, payload):
        try:
            h = int(payload)
            if 0 <= h <= 48:
                self.min_seconds_between_watering_config = h * 3600
                self.send_system_message_mqtt(f"Lock: {h}h", force=True)
                self.play_setting_change_sound()
            self.send_blynk_value_mqtt(self.VPIN_WATERING_LOCKOUT_HOURS, h)
        except Exception as e:
            print(f"Lockout error: {e}")
            self.send_system_message_mqtt(f"Lockout error: {e}")

    def _handle_manual_duration(self, payload):
        try:
            s = int(payload)
            if 1 <= s <= 60:
                self.pump_run_duration_manual_s = s
                self.send_system_message_mqtt(f"Manual: {s}s", force=True)
                self.play_setting_change_sound()
            self.send_blynk_value_mqtt(self.VPIN_MANUAL_WATERING_DURATION_S, s)
        except Exception as e:
            print(f"Manual duration error: {e}")
            self.send_system_message_mqtt(f"Manual duration error: {e}")

    def _handle_auto_duration(self, payload):
        try:
            s = int(payload)
            if 1 <= s <= 60:
                self.pump_run_duration_auto_s = s
                self.send_system_message_mqtt(f"Auto: {s}s", force=True)
                self.play_setting_change_sound()
            self.send_blynk_value_mqtt(self.VPIN_AUTO_WATERING_DURATION_S, s)
        except Exception as e:
            print(f"Auto duration error: {e}")
            self.send_system_message_mqtt(f"Auto duration error: {e}")

    def _handle_soil_threshold(self, payload):
        try:
            threshold = int(payload)
            if 5 <= threshold <= 70:
                self.soil_watering_threshold_config = threshold
                self.send_system_message_mqtt(f"Soil: {threshold}%", force=True)
                self.play_setting_change_sound()
            self.send_blynk_value_mqtt(self.VPIN_SOIL_MOISTURE_THRESHOLD, threshold)
        except Exception as e:
            print(f"Soil threshold error: {e}")
            self.send_system_message_mqtt(f"Soil threshold error: {e}")

    async def manual_water_cycle(self):
        if not self.system_active:
            print("Cannot start manual water: System is OFF.")
            self.send_system_message_mqtt("Cannot start: System OFF", force=True)
            return
        if self.current_water_percent < 20:
            print("Cannot start manual water: Water level below 20%.")
            self.send_system_message_mqtt("Cannot start: Low water", force=True)
            return
        if self.pump_pin.value() == 0:
            print(f"Manual watering: {self.pump_run_duration_manual_s}s")
            self.send_system_message_mqtt(f"Manual watering: {self.pump_run_duration_manual_s}s", force=True)
            self.play_watering_action_sound(start=True)
            self.pump_pin.on()
            self.update_blynk_mqtt_pump_status()
            await asyncio.sleep(self.pump_run_duration_manual_s)
            self.pump_pin.off()
            self.play_watering_action_sound(start=False)
            self.update_blynk_mqtt_pump_status()
            self.last_watering_s = utime.time()
            print("Manual watering finished.")
            self.send_system_message_mqtt("Manual watering done", force=True)

    def blynk_mqtt_disconnected_callback(self):
        # MQTT disconnected
        print("Device: MQTT Connection Lost.")
        self.send_system_message_mqtt("Device: MQTT Connection Lost")

    def print_sensor_data_to_terminal(self):
        # Print sensor data to terminal
        current_time = utime.time()
        if current_time - self.last_system_message_s >= 15:  # Print every 15 seconds
            print("\n=== System Status ===")
            
            # Format time nicely
            dt = self.rtc.datetime()
            print(f"Time: {dt[2]:02d}/{dt[1]:02d}/{dt[0]} {dt[4]:02d}:{dt[5]:02d}:{dt[6]:02d}")
            
            print(f"Soil Moisture: {self.current_soil_percent}%")
            print(f"Water Level: {self.current_water_percent}%")
            print(f"Light Level: {self.current_light_percent}%")
            print(f"Temperature: {self.cached_temp}°C")
            print(f"Humidity: {self.cached_hum}%")
            
            # Show last watering time in hours and minutes
            if self.last_watering_s > 0:
                elapsed_seconds = current_time - self.last_watering_s
                elapsed_hours = elapsed_seconds // 3600
                elapsed_minutes = (elapsed_seconds % 3600) // 60
                print(f"Last Watered: {elapsed_hours}h {elapsed_minutes}m ago")
            else:
                print("Last Watered: Never")
            
            # Show system status
            print(f"System Status: {'Online' if self.system_active else 'Offline'}")
            
            # Show last sensor update time
            if self.last_sensor_update_s > 0:
                elapsed_seconds = current_time - self.last_sensor_update_s
                elapsed_minutes = elapsed_seconds // 60
                print(f"Last Sensor Update: {elapsed_minutes}m ago")
            else:
                print("Last Sensor Update: Never")
            
            # System messages
            if self.current_water_percent < 20:
                print("WARNING: Low water level!")
            if self.current_soil_percent < self.soil_watering_threshold_config:
                print("INFO: Soil moisture below threshold")
            if self.current_light_percent < self.THRESHOLD_LIGHT_INSUFFICIENT:
                print("INFO: Insufficient light level")
            
            print("===================\n")
            self.last_system_message_s = current_time

    def toggle_system_power(self):
        current_time_ms = utime.ticks_ms()
        if utime.ticks_diff(current_time_ms, self.last_button_press_time_ms) > self.button_debounce_duration_ms:
            self.last_button_press_time_ms = current_time_ms
            self.system_active = not self.system_active
            if self.system_active:
                print("System ON")
                # Play startup sound immediately
                self.play_startup_sound()
                self.loop.create_task(self.read_all_sensors_sequentially())
                self.update_blynk_http()
            else:
                print("System OFF")
                self.play_shutdown_sound()
                self.pump_pin.off()
                self.update_blynk_mqtt_pump_status()
                self.low_water_alarm_active = False
            return True
        return False