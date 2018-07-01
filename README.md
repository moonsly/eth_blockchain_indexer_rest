# eth_blockchain_indexer_rest
simple version of Etherscan - Ethereum blockchain indexer with REST API

# INSTALL
To run indexer you need Python3.5, after that:
1) Install dependencies in your virtualenv:

```
pip install -r requirements.txt
```

2) Create your PostgreSQL database, then create schema and indexes:

```
cat schema.sql | psql database_name
```

3) Add tokens fixture to avoid long updates of token's quantity:

```cat fixtures/tokens.sql | psql database_name```

4) Set your infura API key, db name, user, password in config.py.

5) Run blockchain indexer - by default it starts parsing from 'latest' block, if you inserted some block with number=block.id - it starts from that block.
It can recover automatically after failing and should be placed to supervisrod config.

```
. env/bin/activate
python3 ./pool.py debug
```

6) Add token updater to crontab:
```
* * * * */5 /your_env/python3 /path_to/token_info_updater.py
```

7) Start REST on localhost:
```
python ./rest_simple.py 

 * Serving Flask app "rest_simple" (lazy loading)
 * Environment: production
   WARNING: Do not use the development server in a production environment.
   Use a production WSGI server instead.
 * Debug mode: on
 * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
 ```
 
 Great! Now you should have some blockchain records in your database (parsed by pool.py) and you can filter your blockchain data via REST on URL
 http://127.0.0.1:5000/api
 
