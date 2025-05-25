# --- WiFi Configuration ---
WIFI_SSID = "ASUS"
WIFI_PASS = "224516987324AApR34" 

# --- Blynk Project Configuration ---
BLYNK_TEMPLATE_ID = "TMPL4TdDES3vm"
BLYNK_TEMPLATE_NAME = "Plant"
BLYNK_AUTH_TOKEN = "6ySH9nvj1lCxlPRCtcbyCP0Ex3d6WZ-n" 
BLYNK_MQTT_BROKER = "fra1.blynk.cloud"  # Blynk server for MQTT and HTTP API
DEVICE_ID = "Pico"                       # Unique Device Identifier for MQTT topics
BLYNK_MQTT_PORT = 8883                   # Secure MQTT port

# --- Hardware Pin Configuration ---
PIN_SOIL_MOISTURE_ADC = 28  # ADC pin for soil moisture sensor
PIN_SOIL_MOISTURE_VCC = 17  # VCC control pin for soil moisture sensor
PIN_WATER_LEVEL_ADC = 26    # ADC pin for water level sensor (VCC direct to 3.3V)
PIN_LDR_ADC = 27            # ADC pin for LDR sensor
PIN_DHT11_DATA = 10         # Data pin for DHT11 sensor
PIN_PUMP_CONTROL = 12       # GPIO pin for the water pump control
PIN_BUZZER = 18             # GPIO pin for the passive buzzer
PIN_SYSTEM_POWER_BUTTON = 5 # Physical power button

# --- Blynk Virtual Pin Configuration ---
VPIN_SOIL_MOISTURE_PERCENT = 0    # Soil Moisture Percentage
VPIN_LIGHT_LEVEL_PERCENT = 1      # Light Intensity Percentage
VPIN_TEMPERATURE = 2              # Temperature in Celsius
VPIN_HUMIDITY = 3                 # Ambient Humidity Percentage
VPIN_PUMP_SWITCH = 4              # Manual Pump Control from Blynk
VPIN_WATER_LEVEL_PERCENT = 5      # Water Level Percentage
VPIN_SYSTEM_MESSAGE = 6           # System Status/Warning Messages
VPIN_LAST_WATERING_TIME = 7       # Last Watering Time
VPIN_WATERING_LOCKOUT_HOURS = 8   # Watering Lockout Period in Hours
VPIN_MANUAL_WATERING_DURATION_S = 9  # Manual Watering Duration in Seconds
VPIN_AUTO_WATERING_DURATION_S = 10   # Auto Watering Duration in Seconds
VPIN_SOIL_MOISTURE_THRESHOLD = 11    # Soil Moisture Watering Threshold

# --- Sensor Calibration Values ---
CAL_SOIL_ADC_DRY = 40409    # ADC value for dry soil (higher value)
CAL_SOIL_ADC_WET = 19060    # ADC value for wet soil (lower value)
CAL_WATER_ADC_EMPTY = 32    # ADC value for empty water tank
CAL_WATER_ADC_FULL = 39641  # ADC value for full water tank
WATER_ADC_LOW_THRESHOLD_VALUE = 29788  # Threshold for low water warning
CAL_LDR_ADC_BRIGHT = 5200   # ADC value for bright light conditions
CAL_LDR_ADC_DARK = 64735    # ADC value for dark conditions

# --- Smart Control Parameters ---
DEFAULT_SOIL_MOISTURE_WATERING_THRESHOLD = 10  # Default soil moisture threshold for watering
THRESHOLD_LIGHT_INSUFFICIENT_PERCENT = 30      # Light level threshold for insufficient light warning
LDR_DAYTIME_MIN_LIGHT_PERCENT = 50             # Minimum light level to consider as daytime

# --- Watering Schedule Configuration ---
WATERING_ALLOWED_HOUR_START = 8  # Start time for allowed watering period (8 AM)
WATERING_ALLOWED_HOUR_END = 20   # End time for allowed watering period (8 PM)
DEFAULT_MIN_SECONDS_BETWEEN_WATERING = 18000   # Minimum time between watering cycles (5 hours)
DEFAULT_PUMP_RUN_DURATION_AUTO_S = 5          # Default duration for automatic watering
LDR_ADC_MAX_DARKNESS_FOR_WATERING = 40000     # Maximum darkness level for watering

# --- System Timing Parameters ---
SENSOR_POWER_ON_DELAY_MS = 100    # Delay after powering on sensors
DHT_READ_INTERVAL_MS = 30000      # Interval between DHT sensor readings
APP_LOOP_INTERVAL_S = 30          # Main application loop interval
LOW_WATER_ALARM_INTERVAL_S = 180  # Interval for low water alarm
HTTP_BLYNK_UPDATE_INTERVAL_S = 3600  # Interval for Blynk HTTP updates

# --- Buzzer Sound Configuration ---
TONE_STARTUP_SEQUENCE = [(523, 100), (659, 100), (784, 100), (1046, 200)]  # C5, E5, G5, C6
TONE_SHUTDOWN_SEQUENCE = [(1046, 200), (784, 100), (659, 100), (523, 100)]  # C6, G5, E5, C5
TONE_WATERING_START = (659, 300)  # E5 note for watering start
TONE_WATERING_END = (523, 300)    # C5 note for watering end
TONE_LOW_WATER_ALARM = (880, 500) # A5 note for low water alarm
TONE_ERROR_BEEP = (300, 500)      # Low frequency for error beep
STARTUP_SOUND_INTER_TONE_DELAY_MS = 150  # Delay between startup sequence tones