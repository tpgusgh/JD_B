import configparser

config = configparser.ConfigParser()
config.read("default.conf")

SERIAL_PORT = config["serial"]["port"]
BAUDRATE = int(config["serial"]["baud_rate"])
