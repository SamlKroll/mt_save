# Как отдать мне `Jeju_World.uexp` (нужно ~2 КБ, не 293 МБ)

## Коротко

От тебя нужен **один кусок** файла `Jeju_World.uexp` — окно, в котором лежат
все 35 домов:

```
смещение 242 123 897, длина 4 222 байта
```

Во всех домах `AreaSize` лежит именно там, и этого окна достаточно, чтобы я
проверил декодер и патчер на реальных данных.

## Что сделать (Windows, PowerShell)

1. Найди распакованный `Jeju_World.uexp` (FModel → `/Game/Maps/Jeju/Jeju_World`,
   либо `repak unpack`). Если он ещё внутри пака — сначала распакуй.
2. Рядом положи `tools/slice_uexp.py` из этого репозитория.
3. Выполни:

```powershell
cd путь\к\папке\с\uexp
python tools\slice_uexp.py --uexp Jeju_World.uexp --out houses_slice.zip
```

Скрипт напечатает размер файла и создаст `houses_slice.zip` примерно на 2–4 КБ.
4. Прикрепи `houses_slice.zip` в чат (или залей куда удобно — файл крошечный).

Если Python на Windows нет — вот эквивалент в PowerShell:

```powershell
$f = "Jeju_World.uexp"; $start = 242123897; $len = 4222
$fs = [System.IO.File]::OpenRead((Resolve-Path $f))
$fs.Seek($start, 'Begin') | Out-Null
$buf = New-Object byte[] $len
$read = $fs.Read($buf, 0, $len)
$fs.Close()
[System.IO.File]::WriteAllBytes("$PWD\houses_slice.bin", $buf[0..($read-1)])
"read $read bytes"
```

Тогда пришли просто `houses_slice.bin` (4 222 байта).

## Почему не целиком

`Jeju_World.uexp` ≈ 293 МБ, а GitHub-релиз отдаётся через
`release-assets.githubusercontent.com` — из моей песочницы этот хост
недоступен (TLS-хендшейк рвётся, `SSL_ERROR_SYSCALL`; `github.com`,
`codeload.github.com` и `api.github.com` при этом работают).
Так что 145-мегабайтный `MotorTown.zip` из релиза `mod-files` я скачать
не могу физически, дело не в правах доступа к репозиторию.

## Если всё-таки хочешь отдать целиком

Работает любой путь, который идёт **не через CDN релизов**:

* **git-папка репозитория** — положить `Jeju_World.uexp` в отдельную папку
  и закоммитить (git-объекты читаются через `github.com`, это проверено).
  Для 293 МБ лучше резать: `python tools/make_chunks.py --file Jeju_World.uexp`
  даст части по 95 МБ + sha256 каждой.
* **Google Drive** — у меня он сейчас выключен; включи в настройках
  подключений, и я попробую забрать через API (хост `www.googleapis.com`
  из песочницы тоже недоступен напрямую, но коннектор работает иначе —
  проверим на месте).
* Прикрепить файл прямо в сообщение.

## Что будет дальше

```bash
python3 tools/patch_world.py --umap Jeju_World.umap --uexp Jeju_World.uexp \
        --usmap Mappings.usmap --size 20000 --dry-run
```

Покажет 35 домов и их текущие `AreaSize`, затем без `--dry-run` запишет
новые значения и соберёт `BuildAnywhere_P.pak`.
