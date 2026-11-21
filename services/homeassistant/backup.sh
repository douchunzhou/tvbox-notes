#!/bin/sh
# Home Assistant 配置备份
# 设计要点：HA 运行时直接打包 SQLite 数据库会拿到损坏的副本，
#           所以备份**排除** *.db / *.db-wal / *.db-shm / *.db-journal。
#           历史状态数据本来也无需备份，重建即可。
set -u

BASE=/mnt/data_sda1/services/homeassistant
SRC="$BASE/config"
DST="$BASE/backups"
KEEP=7
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$DST/ha-config-$STAMP.tar.gz"

mkdir -p "$DST"

if [ ! -d "$SRC" ]; then
  echo "[$(date '+%F %T')] ERROR: $SRC 不存在" >> "$DST/backup.log"
  exit 1
fi

tar -czf "$OUT" -C "$SRC" \
  --exclude='*.db' \
  --exclude='*.db-wal' \
  --exclude='*.db-shm' \
  --exclude='*.db-journal' \
  --exclude='home-assistant_v2.db*' \
  --exclude='tts' \
  --exclude='media' \
  --exclude='.cache' \
  . 2>/dev/null

RC=$?
if [ $RC -ne 0 ]; then
  echo "[$(date '+%F %T')] ERROR: tar 失败 rc=$RC" >> "$DST/backup.log"
  exit $RC
fi

SIZE=$(du -h "$OUT" | cut -f1)
DB_COUNT=$(tar -tzf "$OUT" 2>/dev/null | grep -c '\.db' || true)
echo "[$(date '+%F %T')] OK $OUT ($SIZE) 含db文件数=$DB_COUNT" >> "$DST/backup.log"

# 只保留最近 $KEEP 份
ls -1t "$DST"/ha-config-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r f; do rm -f "$f"; done

exit 0
