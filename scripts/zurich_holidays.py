#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "pandas",
#   "html5lib",
#   "lxml",
# ]
# ///

import re
from datetime import datetime

import pandas as pd


# Holidays we want to extract
days = [
    "Sechseläuten",
    "Knabenschiessen",
]


def extract_date(date_text):
    """Extract and parse a date from text like 'Monday, 15.04.2024' to a datetime object"""
    # Extract the date part (DD.MM.YYYY)
    match = re.search(r"(\d{2}\.\d{2}\.\d{4})", date_text)
    if match:
        date_str = match.group(1)
        return datetime.strptime(date_str, "%d.%m.%Y").date()
    return None


def main():
    # Read the URL that contains multiple years of holiday dates
    url = "https://www.ferienwiki.ch/feiertage/ch/zuerich"
    tables = pd.read_html(url)

    # Dictionary to hold results
    results = {day: [] for day in days}

    # Process all tables (one for each year)
    for table in tables:
        # For each holiday we want to extract
        for holiday in days:
            # Find rows where the first column contains the holiday name
            matching_rows = table[
                table.iloc[:, 0].str.contains(holiday, case=False, na=False)
            ]

            # Process each matching row
            for _, row in matching_rows.iterrows():
                date_text = row.iloc[1]  # Date is in the second column
                date_obj = extract_date(date_text)

                if date_obj:
                    results[holiday].append(date_obj)

    # Generate PostgreSQL INSERT statements
    print("-- PostgreSQL INSERT statements for planning_publicholiday")
    print("-- Generated on", datetime.now().strftime("%Y-%m-%d"))
    print("-- Note: This script assumes you have a unique constraint on (date)")
    print(
        "-- If the constraint doesn't exist, run: ALTER TABLE planning_publicholiday ADD CONSTRAINT unique_date UNIQUE (date);"
    )
    print()

    # Start transaction
    print("BEGIN;")

    # Insert statements with conflict handling (only insert if not exists)
    for holiday, dates in results.items():
        for date in sorted(dates):
            print(
                f"INSERT INTO planning_publicholiday (date, name, fraction) "
                f"VALUES ('{date.strftime('%Y-%m-%d')}', '{holiday}', 0.5) "
                f"ON CONFLICT (date) DO NOTHING;"
            )

    # Commit transaction
    print("COMMIT;")


if __name__ == "__main__":
    main()
