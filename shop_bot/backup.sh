#!/bin/bash
# SQLite backup script
# Add to crontab: 0 3 * * * /opt/shop/backup.sh

set -e

BACKUP_DIR="/opt/shop/backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/shop_$DATE.db"

mkdir -p "$BACKUP_DIR"
cp /opt/shop/shop.db "$FILE"
gzip "$FILE"

# Keep last 14 backups
ls -t "$BACKUP_DIR"/shop_*.db.gz | tail -n +15 | xargs -r rm -f

echo "Backup created: $FILE.gz"
