#!/usr/bin/env python3
import requests
import re
import sys
from decimal import Decimal
from multiprocessing import Pool

from lib import db_connect

""" page parsing:
<td><span title='Total Supply' style='white-space: nowrap;'>Total Supply:</span>
</td>
<td class="tditem">
100,000,000,000 GRAM
</td>

<td>Decimals:&nbsp;
</td>
<td>
18
</td>
"""

def parse_token(wallet):
    # https://etherscan.io/token/0x82d3a142DdD44d2Bd29A683F0691FbEAd3bcCC44
    req = requests.get("https://etherscan.io/token/{}".format(wallet))
    content = req.text
    with open("wallet.html", "w") as f:
        f.write(content)
    sym, supply, decimals = None, None, None
    m1 = re.search(r'Total Supply\:<.*?<td class="tditem">\s*([\d\,\.]+) ([A-Z]+)[^<]*<', content, re.DOTALL|re.MULTILINE)
    if m1:
        supply, sym = m1.group(1), m1.group(2)
        supply = Decimal(supply.replace(",", ""))

    m2 = re.search(r'Decimals.*?<td>\s*(\d+)\s*<', content, re.DOTALL)
    if m2:
        decimals = m2.group(1)

    return (sym, supply, decimals)


def get_token_info(wallet):
    sym, supply, decimals = parse_token(wallet)

    with db_connect() as db:
        cur = db.cursor()
        cur.execute("UPDATE tokens SET symbol=%s, decimals=%s, total_supply=%s WHERE wallet = %s",
            (sym, decimals, supply, wallet))
        db.commit()

        update_single_token_txns(db, wallet)


def update_single_token_txns(db, wallet):
    cur = db.cursor()
    cur.execute("SELECT id, decimals FROM tokens WHERE wallet=%s AND decimals IS NOT NULL", (wallet,))
    rows = cur.fetchall()
    if len(rows) > 0:
        tid, decimals = rows[0]
        cur.execute("UPDATE transactions SET quantity = token_quantity / (10 ^ %s) WHERE token_id=%s AND quantity=0", (decimals, tid))
        db.commit()


def update_all_token_txns(db):
    cur = db.cursor()
    cur.execute("SELECT id, decimals FROM tokens WHERE decimals IS NOT NULL")
    rows = cur.fetchall()
    for row in rows:
        tid, decimals = row
        print("UPDATING {}".format(tid))
        cur.execute("UPDATE transactions SET quantity = token_quantity / (10 ^ %s) WHERE token_id=%s AND quantity=0", (decimals, tid))
        db.commit()


if __name__ == "__main__":
    db = db_connect()
    cur = db.cursor()
    cur.execute("SELECT id, wallet FROM tokens WHERE decimals IS NULL")
    rows = cur.fetchall()
    wallets = []
    for row in rows:
        tid, wallet = row
        wallets.append(wallet)
    
    process_number = 10
    if len(sys.argv) == 2 and sys.argv[1] == "all":
        update_all_token_txns(db)
        sys.exit(0)


    with Pool(process_number) as pool:
        results = pool.map(get_token_info, wallets)
