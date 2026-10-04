"""
Utility functions for basic SQL commands.
"""
import random
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "Table",
    "create_populate_table",
    "get_random_name",
]

@dataclass(frozen=True)
class Column:
    name: str
    db_type: str

@dataclass(frozen=True)
class Table:
    name: str
    schema: type[NamedTuple]

    @property
    def columns(self):
        return tuple(
            Column(name=name, db_type=self.py_to_db(py_type)) # pyright: ignore[reportAny]
            for name, py_type in   # pyright: ignore[reportAny]
            self.schema.__annotations__.items()
        )

    def py_to_db(self, py_type: type) -> str:
        # TODO Other than str->"TEXT", the mappings were not tested
        # TODO The mapping might be custom depending on the needs of the developer / differ by table
        type_map: dict[type, str] = {
            str: "TEXT",
            int: "INTEGER",
            float: "REAL",
            bool: "BOOLEAN",
            type(None): "NULL",
        }

        return type_map[py_type]

def get_random_name() -> tuple[str, str]:
    """
    Gets a random name from the text files in the Names directory.
    """
    male_first_names = _read_name_list("male-first-names.txt")
    female_first_names = _read_name_list("female-first-names.txt")
    last_names = _read_name_list("last-names.txt")

    first_names = male_first_names + female_first_names
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    return first_name.title(), last_name.title()

@cache
def _read_name_list(filename: str) -> list[str]:
    """
    Gets the name files. Assumes these files are in a folder called Names in the same directory as script.
    """
    path = Path(__file__).resolve().parent / "Names" / filename
    with path.open("r", encoding="utf-8") as file:
        return [line.strip() for line in file if line.strip()]

def create_populate_table(
    connection: sqlite3.Connection,
    table: Table,
    rows: Iterable[NamedTuple]
) -> None:
    """
    Creates and populates a table with the given rows.
    """
    _create_table(connection, table)
    _populate_table(connection, table, rows)

def _create_table(connection: sqlite3.Connection, table: Table) -> None:
    """
    Creates a table.
    """
    columns = ", ".join(f"{c.name} {c.db_type}" for c in table.columns)
    cursor = (connection.cursor()
        .execute(f"DROP TABLE IF EXISTS {table.name}")
        .execute(f"CREATE TABLE IF NOT EXISTS {table.name} ({columns})")
    )
    connection.commit()
    cursor.close()

def _populate_table(
    connection: sqlite3.Connection,
    table: Table,
    rows: Iterable[NamedTuple],
) -> None:
    """
    Populates a table with the given rows.
    """
    columns = tuple(c.name for c in table.columns)
    sql_columns = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    query = f"INSERT INTO {table.name} ({sql_columns}) VALUES ({placeholders})"

    values = tuple(tuple(getattr(row, column) for column in columns) for row in rows)
    cursor = connection.executemany(query, values)
    connection.commit()
    cursor.close()
