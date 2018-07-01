CREATE TABLE blocks (
    id INT NOT NULL PRIMARY KEY, block_time TIMESTAMP, inserted TIMESTAMP, parsed_time REAL,
    total_txns INT, token_txns INT, fully_parsed BOOLEAN DEFAULT FALSE, block_hash CHAR(80));
CREATE INDEX ON blocks(block_time);
CREATE INDEX ON blocks(inserted);

CREATE TABLE tokens (id SERIAL PRIMARY KEY, wallet CHAR(42) UNIQUE, symbol CHAR(20), name CHAR(100),
    decimals INT, total_supply DECIMAL(100,5));
CREATE INDEX ON tokens(symbol);

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY, block_id INT, t_from CHAR(42), t_to CHAR(42), quantity DECIMAL(100, 18), input TEXT,
    created TIMESTAMP, confirmed BOOLEAN DEFAULT FALSE, is_token BOOLEAN DEFAULT FALSE, t_hash CHAR(80) NOT NULL,
    token_id INT, token_quantity DECIMAL(100));
CREATE INDEX ON transactions(block_id);
CREATE INDEX ON transactions(t_from);
CREATE INDEX ON transactions(t_to);
CREATE INDEX ON transactions(created);
CREATE INDEX ON transactions(confirmed);
CREATE INDEX ON transactions(token_id);


ALTER TABLE transactions
    ADD CONSTRAINT fk_block
    FOREIGN KEY (block_id)
    REFERENCES blocks(id);

ALTER TABLE transactions
    ADD CONSTRAINT fk_token
    FOREIGN KEY (token_id)
    REFERENCES tokens(id);
