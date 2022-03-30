from __future__ import print_function

import mq
from Adafruit_CCS811 import Adafruit_CCS811
from sds011 import SDS011
import adafruit_bme280

import sys, time, datetime, MySQLdb, signal, busio, serial, struct, board, math
import json, requests
from systemd.journal import JournalHandler
import logging
import os

# mysql server conf vars
mysql_server = os.getenv('MYSQL_SERVER_URL')
mysql_user = os.getenv('MYSQL_USER')
mysql_pass = os.getenv('MYSQL_PASS')
mysql_db = os.getenv('MYSQL_DB')

# openweather conf
api_key = os.getenv('OPENWEATHER_API_KEY')
location_id = os.getenv('OPENWEATHER_LOCATION_ID')
api_units_format = "metric"
endpoint_url = "https://api.openweathermap.org/data/2.5/weather"
url_call = endpoint_url + '?id=' + location_id + '&APPID=' + api_key + '&units=' + api_units_format

# Logging config
# get an instance of the logger object this module will use
logger = logging.getLogger(__name__)

# instantiate the JournaldHandler to hook into systemd
journald_handler = JournalHandler()

# set a formatter to include the level name
journald_handler.setFormatter(logging.Formatter(
    '[%(levelname)s] %(message)s'
))

# add the journald handler to the current logger
logger.addHandler(journald_handler)

# optionally set the logging level
logger.setLevel(logging.DEBUG)


i2c = busio.I2C(board.SCL, board.SDA)

# Configuration for MQ-135 sensor
#mq = MQ()

# Configuration for BME-280 sensor
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

# Configuration for CCS811 sensor
ccs =  Adafruit_CCS811()


sds011 = SDS011("/dev/ttyUSB0", use_query_mode=True)



def sigterm_handler(signal, frame):
    logger.info("Terminating app")
    sys.stdout.write("Terminating app")
    sys.stdout.write()
    sys.exit(0)


def send_mysql_data(sentence):
    try:
        db = MySQLdb.connect(mysql_server, mysql_user, mysql_pass, mysql_db)
        cursor = db.cursor()
        cursor.execute(sentence)
        db.commit()
    except (MySQLdb.Error, MySQLdb.Warning) as e:
        error = "DB operation failed: {}".format(e)
        sys.stderr.write(error)


def read_MQ135():

    perc = mq.MQPercentage()

    sentence = "INSERT INTO gases (LPG, CO, fume) VALUES ({}, {}, {})".format(perc["GAS_LPG"], perc["CO"], perc["SMOKE"])
    logger.info(sentence)
    send_mysql_data(sentence)


def read_CCS811():

    while not ccs.available():
        pass

    temp = ccs.calculateTemperature()
    ccs.tempOffset = temp - 25.0

    attempt = 0
    max_attempts = 10

    while attempt < max_attempts:
        if not ccs.readData():
            CO2 = ccs.geteCO2()
            TVOC = ccs.getTVOC()

            if CO2 is 0:
                logger.info("Incorrect data from CO2 sensor. Reading again")
                attempt += 1
                time.sleep(2)
            else:
                sentence = "INSERT INTO CCS811 (co2, tvoc) VALUES ({}, {})".format(CO2, TVOC)
                logger.info(sentence)
                send_mysql_data(sentence)
                break


def read_BME280():
    response = requests.get(url_call)

    json_data = json.loads(response.text)
    outside_temp = round(json_data["main"]["temp"], 1)
    outside_pressure = json_data["main"]["pressure"]
    outside_humidity = json_data["main"]["humidity"]

    sentence = "INSERT INTO OUTSIDE (temperature, pressure, humidity) VALUES ({}, {}, {})".format(outside_temp, outside_pressure, outside_humidity)
    logger.info (sentence)
    send_mysql_data(sentence)

    bme280.sea_level_pressure = outside_pressure

    temperature = round(bme280.temperature, 1)
    pressure = int(round(bme280.pressure, 0))
    humidity = int(round(bme280.humidity, 0))
    altitude = round(bme280.altitude, 2)

    sentence = "INSERT INTO BME280 (temperature, pressure, humidity, altitude) VALUES ({}, {}, {}, {})".format(temperature, pressure, humidity, altitude)
    logger.info (sentence)
    send_mysql_data(sentence)

def read_SDS011():
    sds011.sleep(sleep=False)
    time.sleep(15)


    attempt = 0
    max_attempts = 10
    while attempt < max_attempts:
        values = sds011.query()
        if values is not None:
            break
        else:
            logger.error("Empty data from PM sensor. Retrying...")
            time.sleep(2)
            attempt += 1

    sds011.sleep()

    if values is not None:
        PM25 = values[0]
        PM10 = values[1]
        sentence = "INSERT INTO SDS011 (pm25, pm10) VALUES ({}, {})".format(PM25, PM10)
        logger.info (sentence)
        send_mysql_data(sentence)
    else:
        logger.error("Unable to read data from sensor")


def main():
    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    while True:
        #read_MQ135()
        read_CCS811()
        read_BME280()
        read_SDS011()

        current_time = datetime.datetime.now().hour
        if current_time in range(8):
            # night time
            logger.info("Sleeping for 1 hour")
            time.sleep(3600)
        else:
            logger.info("Sleeping for 5 minutes")
            time.sleep(300)



if __name__ == '__main__':
    main()
