#!/usr/bin/env python3
import psycopg2
from web3 import Web3, HTTPProvider

from config import db_name, db_user, db_pass, conn_string, infura_url


def db_connect(conn_string=conn_string, db_name=db_name, db_user=db_user, db_pass=db_pass):
    """ get a PG connection, if a connect cannot be made an exception will be raised here """
    if not conn_string:
        conn_string = "host='localhost' dbname='{}' user='{}' password='{}'".format(db_name, db_user, db_pass)
    conn = psycopg2.connect(conn_string)
    return conn


def get_w3():
    """Main Web3 object"""
    return Web3(HTTPProvider(infura_url))


def convert_hex(hb):
    """Get string from HexBytes value"""
    hexdecimal = "0x" + "".join(["{:02x}".format(b) for b in hb])
    return hexdecimal


def make_correct_eth_addr(w3, addr):
    """Get canonical ETH address"""
    w3 = w3 or get_w3()
    return w3.toChecksumAddress(addr)