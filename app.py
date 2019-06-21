from mq import *
import sys, time, MySQLdb, bme280;

# mysql server conf vars
mysql_server="server"
mysql_user="user"
mysql_pass="pass"
mysql_db="db"

mq = MQ135();
bme = bme280.Bme280()
bme.set_mode(bme280.MODE_FORCED)

def send_mysql_data(sentence):
    db = MySQLdb.connect(mysql_server, mysql_user, mysql_pass, mysql_db)
    cursor = db.cursor()
    cursor.execute(sentence)
    db.commit()

def read_MQ():

    perc = mq.MQPercentage()
    sentence = "INSERT INTO gases (LPG, CO, fume) VALUES (%s, %s, %s)".format(perc["GAS_LPG"], perc["CO"], perc["SMOKE"])
    send_mysql_data(sentence)

def read_BME280():

    temperature, pressure, humidity = bme.get_data()
    sentence = "INSERT INTO axentes_fisicos (temperatura, presion, humidade) VALUES (%s, %s, %s)".format(temperature, pressure, humidity)
    send_mysql_data(sentence)


while True:
    read_MQ()
    read_BME280()
    time.sleep(300)
