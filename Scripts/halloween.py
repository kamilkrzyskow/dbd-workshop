"""
Case generation script
"""
import random
import sqlite3
from typing import TypeAlias, TypeVar

import db_utils
import generate_config
from config import *  # for easy access

T = TypeVar("T") # Generic type for functions which and return the same Any type
NeighborhoodInfo: TypeAlias = dict[str, list[Candy]] # Mapping of households to candies_offered

def main() -> None:
    # random.seed(0) # For static random tests

    with sqlite3.connect(CASE_DB_NAME) as connection:
        neighborhood_info, victim_household = generate_neighborhood(connection)
        generate_trick_or_treaters(connection, neighborhood_info, victim_household)

        # # For static random tests
        # with open("db_dump.txt", "w", encoding="utf-8") as db_dump:
        #     db_dump.writelines(line + "\n" for line in connection.iterdump())

    if input("Generate config.json? Yes or No [n]: ").lower().strip().startswith("y"):
        generate_config.main()

def generate_neighborhood(connection: sqlite3.Connection) -> tuple[NeighborhoodInfo, str]:
    """
    Creates the neighborhood table.
    Returns a tuple of...
        neighborhood_info: a map of households to candy limits for the trick-or-treaters tables.
        victim_household: the name/household of the victim
    """
    neighborhood_info: NeighborhoodInfo = {}
    neighborhood_rows: list[NeighborhoodRow] = []
    candies = list(Candy)
    victim_household: str = "" # Empty for not condition
    for i in range(HOUSEHOLD_COUNT):
        candies_offered: list[Candy] = [] # Same as neighborhood_info[household]
        is_caller = i == 0
        is_like_victim = i > 0 and i < 20 # households that have HEALTHY_FOODS and some other third item
        _, household = db_utils.get_random_name()
        if is_caller:
            household = "Hsu" # To be consistent with the voice message
        while household in neighborhood_info:
            # Make sure household name is unique.
            _, household = db_utils.get_random_name()
        if is_caller:
            # Grandma Hsu only gives out raisins
            # The person calling is not the victim
            candies_offered.append(Candy.RAISINS)
        elif is_like_victim:
            # Households that are giving away similar candies as the victim (or are the victim)
            # This is to ensure the player has to GROUP BY by candies
            # Each such household offers all HEALTHY_FOODS + 1 candy from the limited list below
            candy_options = [Candy.CHOCO_BARS, Candy.PEANUT_BARS, Candy.COOKIE, Candy.BROWNIE_BITS, Candy.YUMYUM]
            candies_offered.extend(HEALTHY_FOODS)
            candies_offered.append(random.choice(candy_options))
            if not victim_household:
                # Honestly, it doesn't really matter who the victim is, as long as they have HEALTHY_FOODS
                victim_household = household
        else:
            # The amount of candy types the current household is giving
            household_candies = random.randint(1, 3)
            for _ in range(household_candies):
                # Create candy limits for each household
                candy_options = subtract_list(candies, candies_offered)
                chosen_candy = random.choice(candy_options)
                candies_offered.append(chosen_candy)
        for candy in candies_offered:
            neighborhood_rows.append(NeighborhoodRow(household=household, candy_offered=candy.value))
        neighborhood_info[household] = candies_offered

    neighborhood_rows.sort(key=lambda row: row.household)
    db_utils.create_populate_table(connection, NEIGHBORHOOD, neighborhood_rows)

    return neighborhood_info, victim_household

def generate_trick_or_treaters(connection: sqlite3.Connection, neighborhood: NeighborhoodInfo, victim_household: str) -> None:
    """
    Creates the tables related to trick-or-treaters (trick_or_treaters and candies_taken)
    """
    trick_or_treaters_rows: list[TrickOrTreatersRow] = []
    candies_taken_rows: list[CandiesTakenRow] = []

    # Adding culprit
    add_visited_household(CASE_CULPRIT, neighborhood, candies_taken_rows, trick_or_treaters_rows)
    culprit_candy = subtract_list(neighborhood[victim_household], HEALTHY_FOODS)[0] # There should only be one element left
    add_victim_visit(victim_household, culprit_candy, candies_taken_rows, trick_or_treaters_rows)

    for _ in range(TRICK_OR_TREATER_COUNT):
        # Create trick-or-treaters
        first_name, last_name = db_utils.get_random_name()
        add_visited_household(f"{first_name} {last_name}", neighborhood, candies_taken_rows, trick_or_treaters_rows)

    # Sort by name so that the culprit doesn't appear first
    trick_or_treaters_rows.sort(key=lambda row: row.name)
    candies_taken_rows.sort(key=lambda row: row.name)

    # Add the trick-or-treater tables to the database
    db_utils.create_populate_table(connection, TRICK_OR_TREATERS, trick_or_treaters_rows)
    db_utils.create_populate_table(connection, CANDIES_TAKEN, candies_taken_rows)

def add_visited_household(name: str, neighborhood: NeighborhoodInfo, candies_taken_rows: list[CandiesTakenRow], trick_or_treaters_rows: list[TrickOrTreatersRow]) -> None:
    households_visited = random.sample(list(neighborhood.keys()), random.randint(20, 60))
    for household in households_visited:
        # Add the household each trick-or-treater visited to their table.
        has_taken = False # household is only considered visited if an item is taken
        for candy_taken in neighborhood[household]:
            # And add each candy they take to the `candies_taken` table.
            if skip_if_healthy(candy_taken):
                continue

            has_taken = True
            candies_taken_rows.append(CandiesTakenRow(name=name, candy_taken=candy_taken.value))

        if has_taken:
            trick_or_treaters_rows.append(TrickOrTreatersRow(name=name, household_visited=household))

def add_victim_visit(victim_household: str, victim_candy: Candy, candies_taken_rows: list[CandiesTakenRow], trick_or_treaters_rows: list[TrickOrTreatersRow]) -> None:
    print(f"Suspect went to {victim_household} and took an extra {victim_candy}")
    trick_or_treaters_rows.append(TrickOrTreatersRow(name=CASE_CULPRIT, household_visited=victim_household))
    for _ in range(2):
        candies_taken_rows.append(CandiesTakenRow(name=CASE_CULPRIT, candy_taken=victim_candy.value))

def skip_if_healthy(item: Candy) -> bool:
    # Most trick-or-treaters will skip healthy items
    skip_rate = 0
    if item == Candy.CARROTS:
        skip_rate = 90
    elif item == Candy.RAISINS:
        skip_rate = 70

    return random.randint(1, 100) <= skip_rate

def subtract_list(list1: list[T], list2: list[T]) -> list[T]:
    """
    Helper function that filters out values that are in list2, like for avoiding duplicates
    """
    return [x for x in list1 if x not in list2]

if __name__ == "__main__":
    main()
