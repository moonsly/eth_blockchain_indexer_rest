#!/usr/bin/env python3

import psycopg2
import json
import flask
from flask import request
from datetime import datetime

from lib import db_connect, get_w3, make_correct_eth_addr


app = flask.Flask(__name__)


def db_conn():
    return db_connect()


def to_json(data):
    return json.dumps(data) + "\n"


def resp(code, data):
    return flask.Response(
        status=code,
        mimetype="application/json",
        response=to_json(data)
    )


def affected_num_to_code(cnt):
    code = 200
    if cnt == 0:
        code = 404
    return code


@app.route("/api")
def root():
    return flask.redirect("/api/1.0/transactions")


@app.errorhandler(400)
def page_not_found(e):
    return resp(400, {})


@app.errorhandler(404)
def page_not_found(e):
    return resp(400, {})


@app.errorhandler(405)
def page_not_found(e):
    return resp(405, {})


def serializer_transaction(rows, colnames):
    txns = []
    for row in rows:
        item = dict([(colnames[i], row[i]) for i in range(len(colnames))])
        item["created"] = str(item["created"])
        item["quantity"] = "%.18f" % (item["quantity"])
        item["token_quantity"] = "%.0f" % (item["token_quantity"])
        txns.append(item)
    return txns


@app.route("/api/1.0/transactions", methods=["GET"])
def get_transactions():
    with db_conn() as db:
        cur = db.cursor()
        filter_sql = " WHERE true "
        params, filter_params = {}, []
        params["fromDate"] = int(request.args.get("fromDate", 0))
        if params["fromDate"]:
            filter_sql += "AND created > %s "
            filter_params.append(datetime.fromtimestamp(params["fromDate"]))
        params["toDate"] = int(request.args.get("toDate", 0))
        if params["toDate"]:
            filter_sql += "AND created < %s "
            filter_params.append(datetime.fromtimestamp(params["toDate"]))

        params["fromAddress"] = request.args.get("fromAddress", None)
        if params["fromAddress"]:
            filter_sql += "AND t_from = %s "
            params["fromAddress"] = make_correct_eth_addr(None, params["fromAddress"])
            filter_params.append(params["fromAddress"])
        params["toAddress"] = request.args.get("toAddress", None)
        if params["toAddress"]:
            filter_sql += "AND t_to = %s "
            params["toAddress"] = make_correct_eth_addr(None, params["toAddress"])
            filter_params.append(params["toAddress"])

        page = int(request.args.get("page", 0))
        limit1, limit2 = page * 100, (page + 1) * 100

        sql = "SELECT * FROM transactions " + filter_sql + " ORDER BY created DESC, id DESC OFFSET %s LIMIT %s"
        cur.execute(sql, ( *filter_params, limit1, limit2))
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        txns = serializer_transaction(rows, colnames)

        result = {"page": page, "transactions": txns, "page_size": 100}
        count = 0
        if filter_params:
            count_sql = "SELECT * FROM transactions " + filter_sql
            cur.execute(count_sql, (*filter_params,))
            count_rows = cur.fetchall()
            count = len(count_rows)
            result.update({"total_count": count})

        for k, v in params.items():
            if v:
                result.update({"params": params})
        return resp(200, result)


if __name__ == "__main__":
    app.debug = True  # enables auto reload during development
    app.run()
