# scripts/crypto_browser.py
"""
Simple database browser for viewing and updating crypto symbols
"""
# pylint:disable=broad-exception-caught,trailing-whitespace

import sqlite3


def browse_crypto_table(db_path: str = "crypto_trading.db"):
    """Browse and update crypto table interactively"""

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        while True:
            print("\n" + "=" * 60)
            print("Crypto Database Browser")
            print("=" * 60)

            # Show current symbols
            cursor.execute(
                """
                SELECT symbol, monitored, mid, updated_at 
                FROM crypto 
                ORDER BY monitored DESC, symbol
            """
            )

            rows = cursor.fetchall()
            if not rows:
                print("No crypto symbols found. Run data collector first.")
                break

            print(f"\n{'Status':<10} {'Symbol':<12} {'Price':<12} {'Updated':<20}")
            print("-" * 60)

            for symbol, monitored, price, updated in rows:
                status = "MONITORED" if monitored else "-"
                price_str = f"${price:,.2f}" if price else "No price"
                print(f"{status:<10} {symbol:<12} {price_str:<12} {updated:<20}")

            print(f"\nTotal symbols: {len(rows)}")
            monitored_count = sum(1 for _, monitored, _, _ in rows if monitored)
            print(f"Monitored: {monitored_count}")

            print("\nOptions:")
            print("1. Set symbols as monitored")
            print("2. Remove monitoring")
            print("3. Monitor all")
            print("4. Monitor none")
            print("5. Refresh")
            print("6. Exit")

            choice = input("\nChoice: ").strip()

            if choice == "1":
                symbols = (
                    input("Enter symbols to monitor (space-separated): ")
                    .strip()
                    .upper()
                    .split()
                )
                if symbols:
                    placeholders = ",".join("?" * len(symbols))
                    cursor.execute(
                        f"""
                        UPDATE crypto 
                        SET monitored = 1, updated_at = datetime('now')
                        WHERE symbol IN ({placeholders})
                    """,
                        symbols,
                    )
                    print(f"✅ Updated {cursor.rowcount} symbols")
                    conn.commit()

            elif choice == "2":
                symbols = (
                    input("Enter symbols to stop monitoring: ").strip().upper().split()
                )
                if symbols:
                    placeholders = ",".join("?" * len(symbols))
                    cursor.execute(
                        f"""
                        UPDATE crypto 
                        SET monitored = 0, updated_at = datetime('now')
                        WHERE symbol IN ({placeholders})
                    """,
                        symbols,
                    )
                    print(f"✅ Updated {cursor.rowcount} symbols")
                    conn.commit()

            elif choice == "3":
                confirm = input("Monitor ALL symbols? (y/N): ").strip().lower()
                if confirm == "y":
                    cursor.execute(
                        "UPDATE crypto SET monitored = 1, updated_at = datetime('now')"
                    )
                    print(f"✅ Set {cursor.rowcount} symbols as monitored")
                    conn.commit()

            elif choice == "4":
                confirm = input("Stop monitoring ALL symbols? (y/N): ").strip().lower()
                if confirm == "y":
                    cursor.execute(
                        "UPDATE crypto SET monitored = 0, updated_at = datetime('now')"
                    )
                    print(f"✅ Removed monitoring from {cursor.rowcount} symbols")
                    conn.commit()

            elif choice == "5":
                continue  # Refresh by looping

            elif choice == "6":
                break

            else:
                print("Invalid choice")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    browse_crypto_table()
