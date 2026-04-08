#!/bin/bash
set -e

# Write the Python reimplementation of the COBOL BOOKFORUM program.
#
# COBOL record layouts (no line separators — pure fixed-length binary blocks):
#   ACCOUNTS.DAT  : ID(4) NAME(20) BALANCE(10)         = 34 bytes/record
#   BOOKS.DAT     : ID(4) TITLE(20) OWNER(4)            = 28 bytes/record
#   TRANSACTIONS.DAT: BOOK(4) AMOUNT(10) SELLER(4) BUYER(4) = 22 bytes/record
#   INPUT.DAT     : BUYER(4) SELLER(4) BOOK(4) AMOUNT(10) = 22 bytes
#
# Logic:
#   1. Read one input record from src/INPUT.DAT
#   2. Validate buyer+seller exist in ACCOUNTS, book exists in BOOKS, book.owner == seller
#   3. If valid: debit buyer balance, credit seller balance, transfer book ownership, append transaction

cat > /app/program.py << 'PYEOF'
import sys
from dataclasses import dataclass
from pathlib import Path

ACCOUNTS_PATH = Path("/app/data/ACCOUNTS.DAT")
BOOKS_PATH = Path("/app/data/BOOKS.DAT")
TRANSACTIONS_PATH = Path("/app/data/TRANSACTIONS.DAT")
INPUT_PATH = Path("/app/src/INPUT.DAT")

ACCOUNT_RECORD_SIZE = 34
BOOK_RECORD_SIZE = 28
TRANSACTION_RECORD_SIZE = 22
INPUT_RECORD_SIZE = 22

ACCOUNT_ID_LEN = 4
ACCOUNT_NAME_LEN = 20
ACCOUNT_BALANCE_LEN = 10

BOOK_ID_LEN = 4
BOOK_TITLE_LEN = 20
BOOK_OWNER_LEN = 4

TRANS_BOOK_LEN = 4
TRANS_AMOUNT_LEN = 10
TRANS_SELLER_LEN = 4
TRANS_BUYER_LEN = 4

INPUT_BUYER_LEN = 4
INPUT_SELLER_LEN = 4
INPUT_BOOK_LEN = 4
INPUT_AMOUNT_LEN = 10


@dataclass
class Account:
    account_id: str
    name: str
    balance: int


@dataclass
class Book:
    book_id: str
    title: str
    owner: str


@dataclass
class InputRecord:
    buyer_id: str
    seller_id: str
    book_id: str
    amount: int


def read_input() -> InputRecord:
    raw = INPUT_PATH.read_text()
    offset = 0
    buyer_id = raw[offset : offset + INPUT_BUYER_LEN]
    offset += INPUT_BUYER_LEN
    seller_id = raw[offset : offset + INPUT_SELLER_LEN]
    offset += INPUT_SELLER_LEN
    book_id = raw[offset : offset + INPUT_BOOK_LEN]
    offset += INPUT_BOOK_LEN
    amount = int(raw[offset : offset + INPUT_AMOUNT_LEN])
    return InputRecord(buyer_id=buyer_id, seller_id=seller_id, book_id=book_id, amount=amount)


def read_accounts() -> list[Account]:
    raw = ACCOUNTS_PATH.read_text()
    accounts: list[Account] = []
    pos = 0
    while pos + ACCOUNT_RECORD_SIZE <= len(raw):
        rec = raw[pos : pos + ACCOUNT_RECORD_SIZE]
        account_id = rec[0:ACCOUNT_ID_LEN]
        name = rec[ACCOUNT_ID_LEN : ACCOUNT_ID_LEN + ACCOUNT_NAME_LEN]
        balance = int(rec[ACCOUNT_ID_LEN + ACCOUNT_NAME_LEN : ACCOUNT_RECORD_SIZE])
        accounts.append(Account(account_id=account_id, name=name, balance=balance))
        pos += ACCOUNT_RECORD_SIZE
    return accounts


def write_accounts(accounts: list[Account]) -> None:
    content = "".join(
        f"{acc.account_id}{acc.name}{acc.balance:0{ACCOUNT_BALANCE_LEN}d}"
        for acc in accounts
    )
    ACCOUNTS_PATH.write_text(content)


def read_books() -> list[Book]:
    raw = BOOKS_PATH.read_text()
    books: list[Book] = []
    pos = 0
    while pos + BOOK_RECORD_SIZE <= len(raw):
        rec = raw[pos : pos + BOOK_RECORD_SIZE]
        book_id = rec[0:BOOK_ID_LEN]
        title = rec[BOOK_ID_LEN : BOOK_ID_LEN + BOOK_TITLE_LEN]
        owner = rec[BOOK_ID_LEN + BOOK_TITLE_LEN : BOOK_RECORD_SIZE]
        books.append(Book(book_id=book_id, title=title, owner=owner))
        pos += BOOK_RECORD_SIZE
    return books


def write_books(books: list[Book]) -> None:
    content = "".join(
        f"{book.book_id}{book.title}{book.owner}"
        for book in books
    )
    BOOKS_PATH.write_text(content)


def append_transaction(book_id: str, amount: int, seller_id: str, buyer_id: str) -> None:
    record = f"{book_id}{amount:0{TRANS_AMOUNT_LEN}d}{seller_id}{buyer_id}"
    existing = TRANSACTIONS_PATH.read_text()
    TRANSACTIONS_PATH.write_text(existing + record)


def validate(inp: InputRecord, accounts: list[Account], books: list[Book]) -> bool:
    buyer_found = any(acc.account_id == inp.buyer_id for acc in accounts)
    seller_found = any(acc.account_id == inp.seller_id for acc in accounts)
    book_found = any(book.book_id == inp.book_id for book in books)
    valid_owner = any(
        book.book_id == inp.book_id and book.owner == inp.seller_id
        for book in books
    )
    return buyer_found and seller_found and book_found and valid_owner


def process_transaction(inp: InputRecord, accounts: list[Account], books: list[Book]) -> None:
    for acc in accounts:
        if acc.account_id == inp.buyer_id:
            acc.balance -= inp.amount
        if acc.account_id == inp.seller_id:
            acc.balance += inp.amount
    write_accounts(accounts)

    for book in books:
        if book.book_id == inp.book_id:
            book.owner = inp.buyer_id
    write_books(books)

    append_transaction(inp.book_id, inp.amount, inp.seller_id, inp.buyer_id)


def main() -> None:
    inp = read_input()
    accounts = read_accounts()
    books = read_books()

    if validate(inp, accounts, books):
        process_transaction(inp, accounts, books)
        print("Transaction completed successfully")
    else:
        print("Transaction failed due to validation errors")


if __name__ == "__main__":
    main()
PYEOF

echo "program.py written to /app/program.py"
python /app/program.py
