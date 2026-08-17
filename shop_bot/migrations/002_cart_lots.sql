-- 002: корзина хранит лоты каталога (не только account_id из БД)
ALTER TABLE cart ADD COLUMN item_id INTEGER;
ALTER TABLE cart ADD COLUMN country_code TEXT;
ALTER TABLE cart ADD COLUMN country_name TEXT;
ALTER TABLE cart ADD COLUMN account_type TEXT;
ALTER TABLE cart ADD COLUMN price REAL;
ALTER TABLE cart ADD COLUMN cost_price REAL;
ALTER TABLE cart ADD COLUMN item_age_days INTEGER;
ALTER TABLE cart ADD COLUMN has_avatar INTEGER DEFAULT 0;
ALTER TABLE cart ADD COLUMN reg_date TEXT;
ALTER TABLE cart ADD COLUMN contacts_count INTEGER;
ALTER TABLE cart ADD COLUMN has_premium INTEGER DEFAULT 0;
