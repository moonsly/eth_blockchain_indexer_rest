from hexbytes import HexBytes


INFURA_API_KEY = "ciyB9JQHYCBqgLMKR1Zd"
DECIMALS_ETH = 18
TXN_CONFIRMATIONS = 12

infura_url = "https://mainnet.infura.io/{}".format(INFURA_API_KEY)
transfer_topic = HexBytes('0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef')

db_name, db_user, db_pass = "septemex", "septemex", "septemex"
conn_string = "host='localhost' dbname='{}' user='{}' password='{}'".format(db_name, db_user, db_pass)