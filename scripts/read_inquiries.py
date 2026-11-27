"""Локальный просмотр заявок. Запускайте только на доверенном компьютере."""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings


def main():
    parser = argparse.ArgumentParser(description="Последние заявки (локально)")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    path = Settings().database.resolve()
    if not path.exists():
        print("База ещё не создана. Сначала запустите сайт.")
        return
    # mode=ro гарантирует, что просмотр не изменяет записи.
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT id, name, email, service, message FROM inquiries ORDER BY id DESC LIMIT ?",
            (max(1, min(args.limit, 100)),),
        ).fetchall()
        for row in rows:
            print(f"\nЗаявка #{row[0]} | {row[1]} | {row[2]} | {row[3]}\n{row[4]}")
        print(f"\nПоказано заявок: {len(rows)}")


if __name__ == "__main__":
    main()
