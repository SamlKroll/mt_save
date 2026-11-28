#!/usr/bin/env bash
# Одна команда: заливает Jeju_World.uexp в репозиторий через git (не через релизы).
#   bash tools/push_uexp.sh /путь/к/Jeju_World.uexp
set -euo pipefail

SRC="${1:?укажи путь к Jeju_World.uexp}"
NAME="$(basename "$SRC")"
REMOTE="https://github.com/SamlKroll/mt_save.git"
WORK="$(mktemp -d)"

echo "== 1/4 клонирую репозиторий =="
git clone --depth 1 "$REMOTE" "$WORK/repo" >/dev/null
cd "$WORK/repo"
mkdir -p assets

SZ=$(stat -c%s "$SRC" 2>/dev/null || stat -f%z "$SRC")
echo "== 2/4 $NAME: $SZ байт =="

if [ "$SZ" -lt 95000000 ]; then
    echo "   файл меньше 95 МБ — кладу целиком"
    cp "$SRC" "assets/$NAME"
else
    echo "   файл большой — режу на части по 90 МБ"
    split -b 90m -d -a 2 "$SRC" "assets/$NAME.part"
    ls -l assets/
fi

echo "== 3/4 коммит =="
git add assets
git -c user.name="upload" -c user.email="upload@local" commit -m "assets: $NAME for patching"

echo "== 4/4 push =="
git push origin HEAD:main

echo
echo "готово. части лежат в ветке main, папка assets/"
echo "напиши в чат: залил"
echo "временная копия: $WORK  (можно удалить)"
