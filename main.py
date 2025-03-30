from src.accounts_monitor import update_accounts_info
from src.paradex_pair_metrics import update_metrics
from src.position_manager import TradingManager
from utils.initial_checks import start as start_initial_checks

import questionary


if __name__ == "__main__":
    action = questionary.select(
        "📌 What would you like to do?",
        choices=[
            "1. ⚙️  Start trading",
            "2. 📊 Fetch market data and update active trading pairs (data/active_pairs.xlsx)",
            "3. 🔄 Update account balances and check for open positions (data/accounts.xlsx)",
            "4. 🛑 Close all currently open positions",
            "5. ❌ Exit"
        ]
    ).ask()

    if action.startswith("1"):
        start_initial_checks()
        manager = TradingManager()
        manager.start_trading()

    elif action.startswith("2"):
        update_metrics()

    elif action.startswith("3"):
        update_accounts_info()

    elif action.startswith("4"):
        manager = TradingManager()
        manager.close_all_positions()

    else:
        print("Exited.")
