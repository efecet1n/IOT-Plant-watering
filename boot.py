import time
import network

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        print("WiFi bağlantısı yapılıyor...")
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("WiFi bağlı:", wlan.ifconfig())
    else:
        print("WiFi bağlantısı başarısız!")

# config.py'den bilgileri al
try:
    import config
    connect_wifi(config.WIFI_SSID, config.WIFI_PASS)
except:
    print("WiFi bilgileri eksik veya config.py hatalı.")
