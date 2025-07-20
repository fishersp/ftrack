import configparser

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")
print(config.sections())
print(config["bot"]["TOKEN"])
