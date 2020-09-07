# DL4MAP
Data logger for Media/Digital Art Project

### 1. structure
<img src="_data/structure.jpg" width="50%" height="50%"></img>
<br/><br/>
<img src="_data/IMG_1849.jpg" width="50%" height="50%"></img>
<br/><br/><br/>
<img src="_data/server_message_flow.jpg" width="90%" height="90%"></img>

<br/><br/>
### 2. dependencies
```
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto.service
pip install telepot
pip install urllib3==1.9.1
pip install paho-mqtt
pip install apscheduler
pip install pyOSC
sudo apt install python-pil
```
######  Adafruit Python GPIO Library - deprecated    
######  Adafruit Python SSD1306 - deprecated

<br/><br/>
### 3. references
   * Mosquitto: <https://mosquitto.org/>
   * telepot: <https://telepot.readthedocs.io/en/latest/>
   * paho-mqtt: <https://github.com/eclipse/paho.mqtt.python>
   * APScheduler: <https://apscheduler.readthedocs.io/en/stable/userguide.html>
   * Adafruit Python GPIO Library: <https://github.com/adafruit/Adafruit_Python_GPIO>
   * Adafruit Python SSD1306: <https://github.com/adafruit/Adafruit_Python_SSD1306>
