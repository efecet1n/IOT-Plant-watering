import gc, sys, time, machine, json, asyncio
import config
from umqtt.simple import MQTTClient, MQTTException

def _dummy(*args):
    pass

on_connected = _dummy
on_disconnected = _dummy
on_message = _dummy
firmware_version = "0.1.0"
connection_count = 0

LOGO = r"""
      ___  __          __
     / _ )/ /_ _____  / /__
    / _  / / // / _ \/  '_/
   /____/_/\_, /_//_/_/\_\
          /___/
"""

print(LOGO)

def _parse_url(url):
    try:
        scheme, url = url.split("://", 1)
    except ValueError:
        scheme = None
    try:
        netloc, path = url.split("/", 1)
    except ValueError:
        netloc, path = url, ""
    try:
        hostname, port = netloc.split(":", 1)
    except:
        hostname = netloc
    return scheme, hostname, int(port), path

def _on_message(topic, payload):
    try:
        on_message(topic, payload)
    except Exception as e:
        sys.print_exception(e)

ssl_ctx = None
if sys.platform in ("esp32", "rp2", "linux"):
    import ssl
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED
    ssl_ctx.load_verify_locations(cafile="ISRG_Root_X1.der")

mqtt = MQTTClient(client_id="", server=config.BLYNK_MQTT_BROKER, ssl=ssl_ctx,
                  user="device", password=config.BLYNK_AUTH_TOKEN, keepalive=45)
mqtt.set_callback(_on_message)

async def _mqtt_connect():
    global connection_count
    mqtt.disconnect()
    gc.collect()
    print("Connecting to MQTT broker...")
    try:
        mqtt.connect()
        mqtt.subscribe("downlink/#")
        print("Connected to Blynk.Cloud", "[secure]" if ssl_ctx else "[insecure]")

        info = {
            "type": config.BLYNK_TEMPLATE_ID,
            "tmpl": config.BLYNK_TEMPLATE_ID,
            "ver": firmware_version,
            "rxbuff": 1024
        }
        mqtt.publish("info/mcu", json.dumps(info))
        connection_count += 1
        on_connected()
    except Exception as e:
        print("Connection failed:", e)
        raise

async def task():
    connected = False
    while True:
        await asyncio.sleep_ms(10)
        if not connected:
            if ssl_ctx:
                while not update_ntp_time():
                    await asyncio.sleep(1)
            try:
                await _mqtt_connect()
                connected = True
            except Exception as e:
                if isinstance(e, MQTTException) and (e.value == 4 or e.value == 5):
                    print("Invalid BLYNK_AUTH_TOKEN")
                    await asyncio.sleep(15 * 60)
                else:
                    print("Connection failed:", e)
                    await asyncio.sleep(2)
        else:
            try:
                mqtt.check_msg()
            except Exception as e:
                connected = False
                on_disconnected()
                await asyncio.sleep(2)

def update_ntp_time():
    Jan24 = 756_864_000 if (time.gmtime(0)[0] == 2000) else 1_704_067_200
    if time.time() > Jan24:
        return True

    print("Getting NTP time...")
    import ntptime
    try:
        ntptime.timeout = 5
        ntptime.settime()
        if time.time() > Jan24:
            print("UTC Time:", time2str(time.gmtime()))
            return True
    except Exception as e:
        print("NTP failed:", e)
    return False

def time2str(t):
    y, m, d, H, M, S, w, j = t
    a = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[w]
    return f"{a} {y}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d}"