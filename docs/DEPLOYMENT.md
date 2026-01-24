# Deployment - Architektura Produkcyjna

**Data:** 2026-01-24
**Serwer:** Hetzner CX53 (16 vCPU, 32 GB RAM, 305 GB NVMe)
**Domena:** moja-dzialka.pl (Cloudflare)

---

## 1. Architektura systemu

```
                         ┌─────────────────┐
                         │   Cloudflare    │
                         │  (DNS + SSL)    │
                         │ moja-dzialka.pl │
                         └────────┬────────┘
                                  │ HTTPS :443
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SERWER: 77.42.86.222 (Hetzner CX53)                  │
│                    Ubuntu 24.04 | 16 vCPU | 32 GB RAM                   │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                         NGINX (Host)                            │    │
│  │  :80 → redirect HTTPS | :443 → proxy to containers              │    │
│  │  /api/* → backend:8000 | /* → frontend:3000                     │    │
│  └──────────────────────────────┬──────────────────────────────────┘    │
│                                 │                                       │
│  ┌──────────────────────────────┴──────────────────────────────────┐    │
│  │                    Docker Network: moja-dzialka                 │    │
│  │                                                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │    │
│  │  │   Backend   │  │  Frontend   │  │      Celery Worker      │  │    │
│  │  │   FastAPI   │  │ React/Vite  │  │    (LiDAR processing)   │  │    │
│  │  │   :8000     │  │   :3000     │  │                         │  │    │
│  │  │   2-4 GB    │  │   512 MB    │  │        2 GB             │  │    │
│  │  └──────┬──────┘  └─────────────┘  └───────────┬─────────────┘  │    │
│  │         │                                      │                │    │
│  │  ┌──────┴──────────────────────────────────────┴──────────┐     │    │
│  │  │                    DATABASES                           │     │    │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────┐  │     │    │
│  │  │  │ PostgreSQL│ │   Neo4j   │ │  Milvus   │ │ Redis  │  │     │    │
│  │  │  │  PostGIS  │ │   Graph   │ │  Vectors  │ │ Cache  │  │     │    │
│  │  │  │  :5432    │ │   :7687   │ │  :19530   │ │ :6379  │  │     │    │
│  │  │  │  4-6 GB   │ │  8-10 GB  │ │  4-6 GB   │ │ 1-2 GB │  │     │    │
│  │  │  └───────────┘ └───────────┘ └───────────┘ └────────┘  │     │    │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐             │     │    │
│  │  │  │  MongoDB  │ │   Minio   │ │   Etcd    │             │     │    │
│  │  │  │  Leads    │ │ (Milvus)  │ │ (Milvus)  │             │     │    │
│  │  │  │  :27017   │ │   :9000   │ │   :2379   │             │     │    │
│  │  │  │  1-2 GB   │ │   512 MB  │ │   256 MB  │             │     │    │
│  │  │  └───────────┘ └───────────┘ └───────────┘             │     │    │
│  │  └────────────────────────────────────────────────────────┘     │    │
│  │                                                                 │    │
│  │  ┌───────────────────────────────────────────────────────────┐  │    │
│  │  │                     MONITORING                            │  │    │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐                │  │    │
│  │  │  │Prometheus │ │  Grafana  │ │  Loki     │                │  │    │
│  │  │  │  :9090    │ │   :3001   │ │  :3100    │                │  │    │
│  │  │  └───────────┘ └───────────┘ └───────────┘                │  │    │
│  │  └───────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  Volumes: /var/lib/docker/volumes/moja-dzialka_*                        │
│  Backups: /root/backups/ → S3/external                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Alokacja zasobów

### RAM (32 GB total)

| Usługa | Min | Max | Uzasadnienie |
|--------|-----|-----|--------------|
| **Neo4j** | 6 GB | 10 GB | Heap 4G + page cache dla 155k działek |
| **PostgreSQL** | 4 GB | 6 GB | shared_buffers + work_mem |
| **Milvus** | 3 GB | 5 GB | Vector index w pamięci |
| **Backend** | 2 GB | 4 GB | FastAPI + Claude API calls |
| **Celery** | 1 GB | 2 GB | LiDAR processing |
| **Redis** | 1 GB | 2 GB | Session cache + pub/sub |
| **MongoDB** | 1 GB | 2 GB | Leads, analytics |
| **Minio+Etcd** | 512 MB | 1 GB | Milvus storage |
| **Frontend** | 256 MB | 512 MB | Static files |
| **Monitoring** | 1 GB | 2 GB | Prometheus + Grafana |
| **System/OS** | 2 GB | 4 GB | Nginx, bufory |
| **TOTAL** | ~22 GB | ~38 GB | **OK z marginesem** |

### CPU (16 vCPU)

| Usługa | Cores | Uwagi |
|--------|-------|-------|
| Neo4j | 4 | Query processing |
| PostgreSQL | 4 | Spatial queries |
| Milvus | 2 | Vector search |
| Backend | 2 | API requests |
| Celery | 2 | Background jobs |
| Other | 2 | Redis, Mongo, monitoring |

### Dysk (305 GB, wolne ~268 GB)

| Dane | Rozmiar | Ścieżka |
|------|---------|---------|
| PostgreSQL | 2-5 GB | `/var/lib/docker/volumes/moja-dzialka_postgres_data` |
| Neo4j | 3-8 GB | `/var/lib/docker/volumes/moja-dzialka_neo4j_data` |
| Milvus | 1-2 GB | `/var/lib/docker/volumes/moja-dzialka_milvus_data` |
| MongoDB | 0.5-1 GB | `/var/lib/docker/volumes/moja-dzialka_mongo_data` |
| Docker images | 12 GB | Już pobrane |
| LiDAR cache | 5-20 GB | `/var/lib/docker/volumes/moja-dzialka_lidar_data` |
| Backups | 10-20 GB | `/root/backups/` |
| **TOTAL** | ~50 GB | **200+ GB wolne** |

---

## 3. Struktura plików na serwerze

```
/root/moja-dzialka/
├── docker-compose.yml          # Główna konfiguracja
├── docker-compose.prod.yml     # Override dla produkcji
├── .env                        # Secrets (nie w git!)
├── backend/
│   ├── Dockerfile
│   └── app/
├── frontend/
│   ├── Dockerfile
│   └── dist/                   # Build produkcyjny
├── nginx/
│   ├── nginx.conf
│   └── ssl/                    # Certyfikaty (Cloudflare Origin)
├── scripts/
│   ├── deploy.sh               # Deployment script
│   ├── backup.sh               # Backup script
│   ├── restore.sh              # Restore script
│   └── import-data.sh          # Initial data import
├── data/
│   └── ready-for-import/       # Dane do zaimportowania
├── backups/                    # Lokalne backupy
└── logs/                       # Logi aplikacji
```

---

## 4. Konfiguracja produkcyjna

### 4.1 docker-compose.prod.yml

```yaml
version: '3.8'

services:
  postgres:
    deploy:
      resources:
        limits:
          memory: 6G
        reservations:
          memory: 4G
    environment:
      # Optymalizacja dla 155k działek
      POSTGRES_SHARED_BUFFERS: 2GB
      POSTGRES_WORK_MEM: 256MB
      POSTGRES_MAINTENANCE_WORK_MEM: 512MB
      POSTGRES_EFFECTIVE_CACHE_SIZE: 4GB
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  neo4j:
    deploy:
      resources:
        limits:
          memory: 10G
        reservations:
          memory: 6G
    environment:
      NEO4J_dbms_memory_heap_initial__size: 4G
      NEO4J_dbms_memory_heap_max__size: 6G
      NEO4J_dbms_memory_pagecache_size: 2G
    restart: always

  milvus:
    deploy:
      resources:
        limits:
          memory: 5G
        reservations:
          memory: 3G
    restart: always

  backend:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
    environment:
      DEBUG: "false"
      WORKERS: 4
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
    restart: always

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    deploy:
      resources:
        limits:
          memory: 512M
    restart: always

  redis:
    deploy:
      resources:
        limits:
          memory: 2G
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
    restart: always

  mongo:
    deploy:
      resources:
        limits:
          memory: 2G
    restart: always
```

### 4.2 Nginx config (/etc/nginx/sites-available/moja-dzialka)

```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=ws:10m rate=5r/s;

# Upstream definitions
upstream backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

upstream frontend {
    server 127.0.0.1:3000;
}

# HTTP → HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name moja-dzialka.pl www.moja-dzialka.pl;
    return 301 https://$server_name$request_uri;
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name moja-dzialka.pl www.moja-dzialka.pl;

    # Cloudflare Origin Certificate
    ssl_certificate /root/moja-dzialka/nginx/ssl/cloudflare-origin.pem;
    ssl_certificate_key /root/moja-dzialka/nginx/ssl/cloudflare-origin.key;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;

    # API endpoints
    location /api/ {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for Claude API calls
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # WebSocket for conversation
    location /api/v1/conversation/ws {
        limit_req zone=ws burst=5 nodelay;

        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    location /api/v2/conversation/ws {
        limit_req zone=ws burst=5 nodelay;

        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    # Health check (no rate limit)
    location /health {
        proxy_pass http://backend;
    }

    # Frontend (React app)
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2)$ {
            proxy_pass http://frontend;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}

# Grafana (optional, internal access)
server {
    listen 443 ssl http2;
    server_name grafana.moja-dzialka.pl;

    ssl_certificate /root/moja-dzialka/nginx/ssl/cloudflare-origin.pem;
    ssl_certificate_key /root/moja-dzialka/nginx/ssl/cloudflare-origin.key;

    # IP whitelist (optional)
    # allow YOUR_IP;
    # deny all;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
    }
}
```

---

## 5. Cloudflare Setup

### DNS Records

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | moja-dzialka.pl | 77.42.86.222 | ✅ Proxied |
| A | www | 77.42.86.222 | ✅ Proxied |
| A | grafana | 77.42.86.222 | ✅ Proxied |

### SSL/TLS Settings

1. **SSL Mode:** Full (strict)
2. **Origin Certificate:** Generate in Cloudflare → download → `/root/moja-dzialka/nginx/ssl/`
3. **Always Use HTTPS:** ON
4. **Minimum TLS:** 1.2

### Security Settings

1. **WAF:** ON (Free plan rules)
2. **Bot Fight Mode:** ON
3. **Challenge Passage:** 30 minutes

---

## 6. Skrypty operacyjne

### 6.1 scripts/deploy.sh

```bash
#!/bin/bash
set -e

echo "=== Deploying moja-dzialka ==="
cd /root/moja-dzialka

# Pull latest code
echo "Pulling latest code..."
git pull origin main

# Build and restart services
echo "Rebuilding containers..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache backend frontend

echo "Restarting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Health check
echo "Waiting for services..."
sleep 10
curl -f http://localhost:8000/health || exit 1

echo "=== Deployment complete ==="
docker compose ps
```

### 6.2 scripts/backup.sh

```bash
#!/bin/bash
set -e

BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

echo "=== Starting backup: $DATE ==="
mkdir -p $BACKUP_DIR

# PostgreSQL
echo "Backing up PostgreSQL..."
docker exec moja-dzialka-postgres pg_dump -U app moja_dzialka | gzip > $BACKUP_DIR/postgres_$DATE.sql.gz

# Neo4j
echo "Backing up Neo4j..."
docker exec moja-dzialka-neo4j neo4j-admin database dump neo4j --to-stdout | gzip > $BACKUP_DIR/neo4j_$DATE.dump.gz

# MongoDB
echo "Backing up MongoDB..."
docker exec moja-dzialka-mongo mongodump --archive --gzip --db moja_dzialka > $BACKUP_DIR/mongo_$DATE.archive.gz

# Redis (RDB snapshot)
echo "Backing up Redis..."
docker exec moja-dzialka-redis redis-cli BGSAVE
sleep 5
docker cp moja-dzialka-redis:/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Cleanup old backups
echo "Cleaning up old backups..."
find $BACKUP_DIR -type f -mtime +$RETENTION_DAYS -delete

# Show backup sizes
echo "=== Backup complete ==="
ls -lh $BACKUP_DIR/*_$DATE.*

# Optional: sync to S3
# aws s3 sync $BACKUP_DIR s3://moja-dzialka-backups/
```

### 6.3 scripts/restore.sh

```bash
#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_date>"
    echo "Example: ./restore.sh 20260124_120000"
    exit 1
fi

DATE=$1
BACKUP_DIR="/root/backups"

echo "=== Restoring from backup: $DATE ==="

# Stop backend to prevent writes
docker compose stop backend celery-worker

# PostgreSQL
echo "Restoring PostgreSQL..."
gunzip -c $BACKUP_DIR/postgres_$DATE.sql.gz | docker exec -i moja-dzialka-postgres psql -U app moja_dzialka

# Neo4j
echo "Restoring Neo4j..."
docker compose stop neo4j
gunzip -c $BACKUP_DIR/neo4j_$DATE.dump.gz | docker exec -i moja-dzialka-neo4j neo4j-admin database load neo4j --from-stdin --overwrite-destination
docker compose start neo4j

# MongoDB
echo "Restoring MongoDB..."
docker exec -i moja-dzialka-mongo mongorestore --archive --gzip < $BACKUP_DIR/mongo_$DATE.archive.gz

# Redis
echo "Restoring Redis..."
docker compose stop redis
docker cp $BACKUP_DIR/redis_$DATE.rdb moja-dzialka-redis:/data/dump.rdb
docker compose start redis

# Restart all
docker compose start backend celery-worker

echo "=== Restore complete ==="
```

### 6.4 scripts/import-data.sh

```bash
#!/bin/bash
set -e

DATA_DIR="/root/moja-dzialka/data/ready-for-import"

echo "=== Importing data to databases ==="

# Wait for databases to be ready
echo "Waiting for databases..."
sleep 30

# Import to PostGIS
echo "Importing to PostGIS..."
for gpkg in $DATA_DIR/postgis/*.gpkg; do
    table=$(basename $gpkg .gpkg)
    echo "  - $table"
    ogr2ogr -f "PostgreSQL" \
        PG:"host=localhost port=5432 dbname=moja_dzialka user=app password=$POSTGRES_PASSWORD" \
        "$gpkg" \
        -nln $table \
        -overwrite \
        -progress
done

# Import to Neo4j
echo "Importing to Neo4j..."
python3 /root/moja-dzialka/egib/scripts/pipeline/08_import_neo4j.py

# Generate embeddings and import to Milvus
echo "Generating embeddings..."
python3 /root/moja-dzialka/egib/scripts/pipeline/09_generate_embeddings.py

echo "Importing to Milvus..."
python3 /root/moja-dzialka/egib/scripts/pipeline/10_import_milvus.py

echo "=== Import complete ==="
```

---

## 7. Cron jobs (backup)

```cron
# /etc/cron.d/moja-dzialka

# Daily backup at 3:00 AM
0 3 * * * root /root/moja-dzialka/scripts/backup.sh >> /var/log/moja-dzialka-backup.log 2>&1

# Weekly docker cleanup (Sunday 4:00 AM)
0 4 * * 0 root docker system prune -f >> /var/log/docker-cleanup.log 2>&1

# Check disk space daily
0 6 * * * root df -h / | mail -s "Disk usage moja-dzialka" admin@example.com
```

---

## 8. Monitoring (Grafana + Prometheus)

### docker-compose.monitoring.yml

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: moja-dzialka-prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.2.0
    container_name: moja-dzialka-grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_SERVER_ROOT_URL: https://grafana.moja-dzialka.pl
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3001:3000"
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.7.0
    container_name: moja-dzialka-node-exporter
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    container_name: moja-dzialka-cadvisor
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    ports:
      - "8080:8080"
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

---

## 9. Checklist przed uruchomieniem

### Przygotowanie serwera

- [ ] Cloudflare DNS skonfigurowany
- [ ] Origin Certificate wygenerowany i pobrany
- [ ] `.env` plik z secrets utworzony
- [ ] Nginx config zainstalowany
- [ ] Firewall (ufw) skonfigurowany (80, 443 only)

### Deployment

- [ ] `git clone` repozytorium
- [ ] Dane do importu przesłane (rsync)
- [ ] `docker compose up -d` databases
- [ ] Import danych (`import-data.sh`)
- [ ] `docker compose up -d` (all services)
- [ ] Health check: `curl https://moja-dzialka.pl/health`

### Post-deployment

- [ ] Backup cron job aktywny
- [ ] Monitoring działający
- [ ] SSL sprawdzony (https://www.ssllabs.com/)
- [ ] Test WebSocket connection
- [ ] Test konwersacji z agentem

---

## 10. Szybki start (TL;DR)

```bash
# Na serwerze (moje-dzialki)

# 1. Sklonuj repo
cd /root
git clone git@github.com:MarcinSar/moja-dzialka.git
cd moja-dzialka

# 2. Skonfiguruj secrets
cp .env.example .env
nano .env  # Ustaw hasła i klucze API

# 3. SSL z Cloudflare
mkdir -p nginx/ssl
# Wgraj cloudflare-origin.pem i cloudflare-origin.key

# 4. Uruchom bazy danych
docker compose up -d postgres neo4j milvus redis mongo

# 5. Zaimportuj dane
./scripts/import-data.sh

# 6. Uruchom wszystko
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 7. Skonfiguruj nginx
sudo cp nginx/moja-dzialka.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/moja-dzialka.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 8. Włącz backup
sudo cp scripts/moja-dzialka-cron /etc/cron.d/

# Done!
```
