# Paradex Delta Neutral Bot

Bot for automating delta-neutral positions on Paradex across multiple accounts.

## Setup
- Clone: git clone https://github.com/Pastfin/Paradex-delta-neutral-bot
- Install: pip install -r requirements.txt (use Docker/Linux if issues arise)

## Configuration
- data/accounts.xlsx: Add private_key, address, proxy, is_active
- data/active_pairs.xlsx: Select trading pairs
- data/config.json: Set order_value_usd, accounts_per_trade, etc

## Features
- Start Trading: Opens delta-neutral positions
- Close Positions: Closes all active trades
- Volume Monitoring & Pair Selection: Collects volume data and allows convenient selection of trading pairs

Full guide: [Instructions](https://teletype.in/@pastfin/YN9jReHzZWx)