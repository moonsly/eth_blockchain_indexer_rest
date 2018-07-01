#!/usr/bin/env python3

import time
import json
import sys
from datetime import datetime
from decimal import Decimal
from hexbytes import HexBytes
from multiprocessing import Pool

import psycopg2
import psycopg2.extras
from web3 import Web3, HTTPProvider

from config import INFURA_API_KEY, DECIMALS_ETH, TXN_CONFIRMATIONS, infura_url, transfer_topic
from lib import db_connect, get_w3, convert_hex, make_correct_eth_addr


DEBUG_PRINT = 0

def hex_remove_leading_zeros(hx, is_address=None):
    """Remove leading zeros from input.amount or ETH address"""
    res = "0x"
    i = 0
    if hx.startswith("0x"):
        i = 2

    if int(hx, 16) == 0:
        if is_address:
            return "0x" + "0" * 40
        else:
            return "0x0"

    sym = hx[i]
    while sym == "0":
        i += 1
        sym = hx[i]

    res += hx[i:]

    # ETH address should have always length == 42
    if is_address and len(res) < 42:
        delta = 42 - len(res)
        res = "0x" + "0"*delta + hx[i:]
    return res


def prepare_addr_from_topic(topic):
    return hex_remove_leading_zeros(convert_hex(topic), is_address=True)


def get_txn_receipt(txn_id, w3=None):
    w3 = w3 or get_w3()
    rcpt = None

    if not txn_id:
        return None

    try:
        rcpt = w3.eth.getTransactionReceipt(txn_id)
    except json.decoder.JSONDecodeError as e:
        DEBUG_PRINT and print("JSON decode error")

    return rcpt


def get_eth_transaction_pool(w3, block, db=None):
    """Parse block's transactions, including getting Receipts via processPool"""
    token_txns = 0
    rcpt_txns = []
    txn_dict, txn_ids = {}, []
    """ Необходимые поля транзакции:
    * hash - хэш транзакции
    * block - номер блока, в который включена транзакция, long
    * from - адрес отправителя, хэш
    * to - адрес получателя, хэш
    * quantity - количество, decimal
    * input - input из транзакции
    * timestamp - таймстемп в utc с точностью до мс
    """
    for txn in block.get("transactions"):
        txn_hash = txn.get("hash")
        txn_id = convert_hex(txn_hash)

        txn_data = {}
        txn_data["t_hash"] = txn_hash
        # tx timestamp = block timestamp
        txn_data["timestamp"] = int(block.get("timestamp"))
        txn_data["block_id"] = int(block.get("number"))
        txn_data["quantity"] = txn.get("value") / float(DECIMALS_ETH)
        for fld in ("from", "to", "input"):
            txn_data[fld] = txn.get(fld)

        txn_dict[txn_hash] = txn_data

        txn_ids.append(txn_hash)

        txn_input = txn.get("input")
        if txn_input.startswith("0xa9059cbb"):
            rcpt_txns.append(txn_hash)

        else:
            DEBUG_PRINT and print("skip {}".format(txn_id))

    DEBUG_PRINT and print("Block: {}\nNumber of total/rcpt TXNs: {} / {}".format(
        block.get("number"), len(block.get("transactions")), len(rcpt_txns)))

    if len(rcpt_txns) > 0:
        # Load transactionReceipts in Pool and return the results
        results = []
        process_number = len(rcpt_txns) // 4 or 1
        with Pool(process_number) as pool:
            results = pool.map(get_txn_receipt, rcpt_txns)
            DEBUG_PRINT and print(results)

        for rcpt in results:
            if rcpt == None:
                continue
            rcpt_id = convert_hex(rcpt.get("transactionHash"))
            DEBUG_PRINT and print("TXN {}".format(str(rcpt_id)))

            topics = None
            if rcpt and len(rcpt.get("logs", [])) > 0:
                topics = rcpt.get("logs")[0].get("topics")

            if topics and topics[0] == transfer_topic and len(topics) == 3:
                token_txns += 1
                txn_id = rcpt.get("transactionHash")
                txn_input = txn_dict[txn_id].get("input")
                amount_end = hex_remove_leading_zeros("0x" + txn_input[-24:])
                DEBUG_PRINT and print("AMOUNT input {}\nEND {}".format(txn_input, amount_end))
                amount = int(amount_end, 16)
                from_addr = make_correct_eth_addr(w3, prepare_addr_from_topic(topics[1]))
                to_addr = make_correct_eth_addr(w3, prepare_addr_from_topic(topics[2]))

                token_wallet = txn_dict[txn_id].get("to")
                decimals = 0
                rcpt_data = {}
                rcpt_data["token_quantity"] = amount
                if token_wallet:
                    token_id, decimals = get_or_create_token_id(db, token_wallet)
                    rcpt_data["token_id"] = token_id
                    if decimals:
                        rcpt_data["quantity"] = amount / float(decimals)

                rcpt_data["is_token"] = True
                rcpt_data["to"] = to_addr

                txn_dict[txn_id].update(rcpt_data)

                DEBUG_PRINT and print("It's transfer topic!\nsum: %.12f\nfrom: %s\nto: %s" % (amount, from_addr, to_addr))

    block_id = insert_block(db, block, token_txns)
    confirm_transactions(db, block_id)
    # for empty ETH blocks
    if len(txn_ids) > 0:
        bulk_insert_txns(db, txn_ids, txn_dict, block)

    return (len(block.get("transactions")), token_txns)


def bulk_insert_txns(conn, txn_ids, txn_dict, block):
    """Insert transactions based on parsed data with Receipts, token transfer logs"""
    cursor = conn.cursor()
    query_data = []
    query = """
        INSERT INTO transactions
        (block_id, t_from, t_to, quantity, input, created, t_hash,
        is_token, token_id, token_quantity) VALUES %s;"""

    created = datetime.fromtimestamp(block.timestamp)
    for tid in txn_ids:
        txn = txn_dict[tid]
        query_data.append([
            txn["block_id"], txn["from"], txn["to"], txn["quantity"], txn["input"], created, convert_hex(tid),
            txn.get("is_token", False), txn.get("token_id", None), txn.get("token_quantity", 0)
        ])

    psycopg2.extras.execute_values(
        cursor, query, query_data, template=None, page_size=len(query_data))

    conn.commit()


def confirm_transactions(conn, block_id):
    """Mark transactions as confirmed"""
    cur = conn.cursor()
    query = """UPDATE transactions SET confirmed=true WHERE confirmed=false AND block_id BETWEEN (%s - 2*%s) AND (%s - %s);"""
    cur.execute(query, (block_id, TXN_CONFIRMATIONS, block_id, TXN_CONFIRMATIONS))
    conn.commit()


def insert_block(conn, block, token_txns):
    """Insert current block"""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO blocks (id, block_time, parsed_time, total_txns, token_txns, fully_parsed, block_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;""",
        (block.number, datetime.fromtimestamp(block.timestamp), 0, len(block.transactions), token_txns, True, convert_hex(block.hash)))
    conn.commit()
    return cur.fetchone()[0]


def get_or_create_token_id(conn, wallet):
    """Get existing or create new token by it's wallet"""
    cur = conn.cursor()
    cur.execute("""SELECT id, decimals FROM tokens WHERE wallet=%s;""", (wallet,))
    rows = cur.fetchall()
    if len(rows) > 0:
        return rows[0]

    else:
        cur.execute("""INSERT INTO tokens (wallet) VALUES (%s) RETURNING id;""", (wallet,))
        conn.commit()
        return (cur.fetchone()[0], 0)


def get_last_block_number(conn):
    """Get latest block from current DB"""
    cur = conn.cursor()
    cur.execute("""SELECT MAX(id) FROM blocks WHERE fully_parsed=true""")
    rows = cur.fetchall()
    if len(rows) > 0:
        return rows[0][0]
    else:
        return None


def block_polling(w3, number):
    """Wait for new latest block"""
    while True:
        try:
            block = w3.eth.getBlock(number, True)
            return block
        except KeyError as e:
            pass

        time.sleep(0.3)


if __name__ == "__main__":
    w3 = get_w3()
    db = db_connect()
    if len(sys.argv) == 2 and sys.argv[1] == "debug":
        DEBUG_PRINT = 1

    # recover block number from DB or start from current ETH block
    last_block = get_last_block_number(db)
    block_number = 0
    if last_block:
        block_number = last_block + 1
    else:
        block_number = w3.eth.blockNumber

    times = []
    total_txns = 0
    while True:
        start = time.time()
        # block = w3.eth.getBlock("latest", True)
        block = None
        while not block:
            block = block_polling(w3, block_number)
        waiting = time.time() - start

        total_txns += len(block.get("transactions", []))
        DEBUG_PRINT and print("--- BLOCK {block}: {time}".format(time=datetime.now(), block=block.get("number")))
        DEBUG_PRINT and print("BLOCK FOR: {}".format(time.time() - start))

        (total_tx, tokens_tx) = get_eth_transaction_pool(w3, block, db)
        delta = time.time() - waiting - start

        DEBUG_PRINT and print("BLOCK {} TXNs total / tokens {} / {} DONE FOR: {}".format(block.number, total_tx, tokens_tx, delta))

        block_number += 1
        times.append(delta)

    DEBUG_PRINT and print("\nBLOCK ITERATIONS: {}\nTOTAL TIME: {}\nAVG TIME: {}".format(len(times), sum(times), sum(times)/len(times)))
    DEBUG_PRINT and print("TOTAL TXNs: {}\nTOKEN TXNs: {} ({})".format(total_txns, token_txns, 100 * token_txns/total_txns))
