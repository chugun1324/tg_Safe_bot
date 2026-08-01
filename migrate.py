#!/usr/bin/env python3
"""
Migration script to add profile fields to users and create portfolio table.
Run this before starting the bot with new models.
"""
import asyncio
import sqlite3
from pathlib import Path


async def apply_migration():
    db_path = Path(__file__).parent / "artsecure.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Migration will be applied on first bot start.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if migration is already applied
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        migrations_needed = []
        if "bio" not in columns:
            migrations_needed.append("bio")
        if "is_available" not in columns:
            migrations_needed.append("is_available")
        if "completed_orders_count" not in columns:
            migrations_needed.append("completed_orders_count")
        if "rating" not in columns:
            migrations_needed.append("rating")
        if "last_offered_at" not in columns:
            migrations_needed.append("last_offered_at")

        if not migrations_needed:
            print("✓ All migrations already applied")
            return

        print(f"Applying migrations: {', '.join(migrations_needed)}...")

        # Add new columns to users table
        if "bio" in migrations_needed:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT NULL")
        if "is_available" in migrations_needed:
            cursor.execute("ALTER TABLE users ADD COLUMN is_available BOOLEAN DEFAULT 1")
        if "completed_orders_count" in migrations_needed:
            cursor.execute("ALTER TABLE users ADD COLUMN completed_orders_count INTEGER DEFAULT 0")
        if "rating" in migrations_needed:
            cursor.execute("ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0")
        if "last_offered_at" in migrations_needed:
            cursor.execute("ALTER TABLE users ADD COLUMN last_offered_at TIMESTAMP DEFAULT NULL")

        # Create portfolio table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist_id INTEGER NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT DEFAULT NULL,
                display_order INTEGER DEFAULT 0,
                file_id VARCHAR(255) DEFAULT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (artist_id) REFERENCES users(id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_artist_id ON portfolio(artist_id)")

        # Update existing users
        cursor.execute("UPDATE users SET is_available = 1 WHERE is_available IS NULL")
        cursor.execute("UPDATE users SET completed_orders_count = 0 WHERE completed_orders_count IS NULL")
        cursor.execute("UPDATE users SET rating = 0 WHERE rating IS NULL")

        conn.commit()
        print("✓ Migration applied successfully")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(apply_migration())
