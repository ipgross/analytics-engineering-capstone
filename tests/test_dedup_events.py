"""
Test script: verify dedup logic in merge_events() for ds=2023-12-23.

Steps:
1. Show current duplicate state
2. Run the fixed dedup DELETE
3. Show post-dedup state
4. (Optional) Re-run MERGE to verify clean result

Usage:
    python tests/test_dedup_events.py
"""
import snowflake.connector

# Connection config (from include/capstone/config.py)
CONN_PARAMS = {
    "user": "ipgross",
    "password": "2qj!sZw8VQ6YX%FN",
    "account": "aab46027.us-west-2",
    "warehouse": "COMPUTE_WH",
    "database": "DATAEXPERT_STUDENT",
    "role": "ALL_USERS_ROLE",
}
TABLE = "ipgross.hist_nba_events"
TEST_DATE = "2023-12-23"


def run():
    conn = snowflake.connector.connect(**CONN_PARAMS)
    cursor = conn.cursor()

    try:
        # Step 1: Check for duplicates
        print(f"=== BEFORE: Checking duplicates for ds={TEST_DATE} ===")
        cursor.execute(f"""
            SELECT event_id, COUNT(*) AS cnt
            FROM {TABLE}
            WHERE ds = '{TEST_DATE}'
            GROUP BY event_id
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        """)
        dupes = cursor.fetchall()
        if not dupes:
            print("No duplicates found! Nothing to fix.")
            return

        total_extra = sum(cnt - 1 for _, cnt in dupes)
        print(f"Found {len(dupes)} event_ids with duplicates ({total_extra} extra rows):")
        for event_id, cnt in dupes[:10]:
            print(f"  event_id={event_id}  count={cnt}")
        if len(dupes) > 10:
            print(f"  ... and {len(dupes) - 10} more")

        # Show total row count for this date
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE ds = '{TEST_DATE}'")
        total_before = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(DISTINCT event_id) FROM {TABLE} WHERE ds = '{TEST_DATE}'")
        distinct_before = cursor.fetchone()[0]
        print(f"\nTotal rows: {total_before}  |  Distinct event_ids: {distinct_before}")

        # Step 2: Run the fixed dedup DELETE
        print(f"\n=== RUNNING DEDUP DELETE ===")
        cursor.execute(f"""
            DELETE FROM {TABLE}
            WHERE ds = '{TEST_DATE}'
            AND event_id IN (
                SELECT event_id
                FROM {TABLE}
                WHERE ds = '{TEST_DATE}'
                GROUP BY event_id
                HAVING COUNT(*) > 1
            )
        """)
        deleted = cursor.rowcount
        print(f"Deleted {deleted} rows (all copies of duplicated event_ids)")

        # Step 3: Check state after dedup
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE ds = '{TEST_DATE}'")
        total_after = cursor.fetchone()[0]
        cursor.execute(f"SELECT COUNT(DISTINCT event_id) FROM {TABLE} WHERE ds = '{TEST_DATE}'")
        distinct_after = cursor.fetchone()[0]
        print(f"\n=== AFTER DEDUP ===")
        print(f"Total rows: {total_after}  |  Distinct event_ids: {distinct_after}")
        print(f"Rows removed: {total_before - total_after}")

        # Step 4: Verify no more duplicates
        cursor.execute(f"""
            SELECT event_id, COUNT(*) AS cnt
            FROM {TABLE}
            WHERE ds = '{TEST_DATE}'
            GROUP BY event_id
            HAVING COUNT(*) > 1
        """)
        remaining_dupes = cursor.fetchall()
        if remaining_dupes:
            print(f"\nWARNING: Still {len(remaining_dupes)} duplicated event_ids remaining!")
        else:
            print("\nNo duplicates remaining.")

        # Step 5: Note which event_ids were deleted (need re-insert from staging or re-run)
        print(f"\n=== NOTE ===")
        print(f"{len(dupes)} event_ids were fully deleted and need re-insertion.")
        print(f"To restore them, re-run the events DAG for ds={TEST_DATE}.")
        print(f"Or run: the MERGE step will re-insert from staging if stg data exists.")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run()
