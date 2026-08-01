-- Migration: Add profile fields to users table and create portfolio table
-- Date: 2026-07-30
-- Description: Add bio, is_available, completed_orders_count, rating to users and create portfolio table

-- Add new columns to users table
ALTER TABLE users ADD COLUMN bio TEXT DEFAULT NULL;
ALTER TABLE users ADD COLUMN is_available BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN profile_visible BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN completed_orders_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0;

-- Create portfolio table
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
);

CREATE INDEX IF NOT EXISTS idx_portfolio_artist_id ON portfolio(artist_id);

-- Update existing users to set default values
UPDATE users SET is_available = 1 WHERE is_available IS NULL;
UPDATE users SET profile_visible = 1 WHERE profile_visible IS NULL;
UPDATE users SET completed_orders_count = 0 WHERE completed_orders_count IS NULL;
UPDATE users SET rating = 0 WHERE rating IS NULL;
