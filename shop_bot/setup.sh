#!/bin/bash
# Автоматическая настройка сервера для Telegram Shop Bot
# Запускать от root: sudo bash setup.sh

set -e

PROJECT_DIR="/opt/shop"
USER="shop"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Настройка сервера для Shop Bot ===${NC}"

# 1. Обновление системы
echo -e "${YELLOW}[1/8] Обновление системы...${NC}"
apt-get update && apt-get upgrade -y

# 2. Создание пользователя
echo -e "${YELLOW}[2/8] Создание пользователя $USER...${NC}"
if ! id "$USER" &>/dev/null; then
    useradd -m -s /bin/bash "$USER"
    usermod -aG sudo "$USER"
fi

# 3. Установка зависимостей
echo -e "${YELLOW}[3/8] Установка зависимостей...${NC}"
apt-get install -y     python3 python3-pip python3-venv     redis-server     nginx     fail2ban     ufw     certbot python3-certbot-nginx     git curl wget htop

# 4. Настройка Redis
echo -e "${YELLOW}[4/8] Настройка Redis...${NC}"
systemctl enable redis-server
systemctl start redis-server

# 5. SSH Hardening
echo -e "${YELLOW}[5/8] Настройка SSH...${NC}"
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
sed -i 's/^#*ClientAliveInterval.*/ClientAliveInterval 300/' /etc/ssh/sshd_config
sed -i 's/^#*ClientAliveCountMax.*/ClientAliveCountMax 2/' /etc/ssh/sshd_config

systemctl restart sshd

echo -e "${YELLOW}[SSH] Проверка настроек...${NC}"
if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config && grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config; then
    echo -e "${GREEN}✅ SSH hardening применён${NC}"
else
    echo -e "${RED}⚠️ SSH hardening не применён полностью!${NC}"
fi

echo -e "${RED}ВАЖНО: Убедитесь, что у вас есть SSH-ключ перед отключением пароля!${NC}"

# 6. Fail2ban
echo -e "${YELLOW}[6/8] Настройка Fail2ban...${NC}"
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-botsearch]
enabled = true
port = http,https
filter = nginx-botsearch
logpath = /var/log/nginx/access.log
maxretry = 5
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# 7. UFW Firewall
echo -e "${YELLOW}[7/8] Настройка фаервола...${NC}"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# 8. Swap
echo -e "${YELLOW}[8/8] Настройка swap...${NC}"
if ! swapon --show | grep -q "/swapfile"; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# 9. Создание проекта
echo -e "${YELLOW}[9/9] Настройка проекта...${NC}"
mkdir -p "$PROJECT_DIR"
chown "$USER:$USER" "$PROJECT_DIR"

# Генерация WEBHOOK_SECRET
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo -e "${GREEN}WEBHOOK_SECRET сгенерирован: $WEBHOOK_SECRET${NC}"

# Создание .env шаблона
cat > "$PROJECT_DIR/.env" << EOF
BOT_TOKEN=
LZT_TOKEN=
ADMIN_ID=
ADMIN_CHAT_ID=
BACKUP_BOT_TOKENS=8673748823:AAGAFzQfInhjwsQr209SX-aEgROffBCRmBU,8955559174:AAGi6HjVzUNBKLNHkKBN5T05VlJ4iJoDFNA
DATABASE_URL=sqlite:///app/shop.db
REDIS_URL=redis://localhost:6379/0
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_PATH=/webhook
WEBHOOK_URL=https://your-domain.com/webhook
WEBHOOK_SECRET=$WEBHOOK_SECRET
TELEGRAM_API_ID=0
TELEGRAM_API_HASH=
MIN_LZT_BALANCE=1000
LZT_RATE_LIMIT=0.2
USER_BUY_COOLDOWN=10
SENTRY_DSN=
CF_MODE=false
EOF

chmod 600 "$PROJECT_DIR/.env"
chown "$USER:$USER" "$PROJECT_DIR/.env"

# Проверка fail2ban
if systemctl is-active --quiet fail2ban; then
    echo -e "${GREEN}✅ Fail2ban активен${NC}"
else
    echo -e "${RED}⚠️ Fail2ban НЕ запущен! Запустите: systemctl start fail2ban${NC}"
fi

# Cron для очистки логов
echo -e "${YELLOW}[Дополнительно] Настройка очистки логов...${NC}"
(crontab -l 2>/dev/null; echo "0 4 * * * cd $PROJECT_DIR && python cleanup_logs.py >> /var/log/shop_cleanup.log 2>&1") | crontab -

# Права на cleanup_logs
chown "$USER:$USER" "$PROJECT_DIR/cleanup_logs.py"
chmod +x "$PROJECT_DIR/cleanup_logs.py"

echo -e "${GREEN}=== Настройка завершена! ===${NC}"
echo -e "${YELLOW}Следующие шаги:${NC}"
echo "1. Скопируйте файлы проекта в $PROJECT_DIR"
echo "2. Отредактируйте $PROJECT_DIR/.env (BOT_TOKEN, LZT_TOKEN, ADMIN_ID и т.д.)"
echo "3. Настройте nginx: sudo cp nginx.conf /etc/nginx/sites-available/shop && sudo ln -s /etc/nginx/sites-available/shop /etc/nginx/sites-enabled/"
echo "4. Получите SSL: sudo certbot --nginx -d your-domain.com"
echo "5. Запустите: cd $PROJECT_DIR && docker-compose up -d"
echo ""
echo -e "${RED}ВАЖНО: Загрузите свой SSH публичный ключ перед выходом!${NC}"
echo "ssh-copy-id -i ~/.ssh/id_rsa.pub $USER@$(hostname -I | awk '{print $1}')"
