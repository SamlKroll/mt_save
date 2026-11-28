# Как отдать `Jeju_World.uexp` — рабочий способ (git, не релиз)

## Ситуация

Файл в релизе есть (`mod-files` → `Jeju_World.uexp`, 306 853 982 байта),
но **релизы GitHub мне недоступны**: любой asset отдаётся через
`release-assets.githubusercontent.com`, а этот хост из моей песочницы
не открывается — обрыв на TLS-хендшейке (`SSL_ERROR_SYSCALL`).

Проверено вдоль и поперёк:

| Способ | Результат |
|---|---|
| `gh release download` | EOF на `release-assets.githubusercontent.com` |
| `curl` по `releases/download/...` | 302 → то же самое |
| `gh api .../assets/802438269 -H "Accept: application/octet-stream"` | 302 → то же самое |
| `curl -r 0-1023` (Range) | 302 → то же самое |
| `github.com` / `api.github.com` / `codeload.github.com` | ✅ работают |

**git при этом работает.** Проверил специально: ленивый fetch 21-мегабайтного
блоба `Jeju_World.ubulk` из свежего клона проходит без проблем.

## Что сделать (одна команда)

**Windows (PowerShell), из любой папки:**

```powershell
powershell -ExecutionPolicy Bypass -File mod_build_anywhere\tools\push_uexp.ps1 -Source C:\path\Jeju_World.uexp
```

Скрипт сам клонирует репозиторий, при необходимости режет файл на части по
90 МБ, коммитит в `assets/` и пушит в `main`. Ничего настраивать не надо,
кроме установленного git.

**Linux / macOS:**

```bash
bash tools/push_uexp.sh /путь/Jeju_World.uexp
```

Потом напиши в чат «залил».

## Что сделать вручную (2 команды)

В той же папке, где лежит `Jeju_World.uexp`:

```bash
git clone https://github.com/SamlKroll/mt_save.git mt-upload
cd mt-upload
mkdir -p assets
cp ../Jeju_World.uexp assets/
git add assets/Jeju_World.uexp
git commit -m "add Jeju_World.uexp for patching"
git push
```

`git push` пойдёт через `github.com` — это единственный путь, который здесь
не блокируется. 293 МБ он примет (лимит на файл — 100 МБ только для
`github.com/.../blob/...` веб-загрузки; обычный push держит до 2 ГБ,
предупреждение начнётся от 50 МБ, ошибка — от 100 МБ **на файл**, поэтому
если GitHub откажет, используй вариант с частями ниже).

Потом напиши мне «залил» — я заберу файл через git и сразу прогоню патчер.

### Если push ругается на размер (файл >100 МБ)

```bash
python3 tools/make_chunks.py --file assets/Jeju_World.uexp --outdir assets/chunks
git add assets/chunks
git commit -m "add Jeju_World.uexp in 95MB chunks"
git push
```

На моей стороне есть `tools/join_chunks.py` (соберёт части обратно и сверит
sha256). Части по 95 МБ проходят гарантированно.

### Совсем без git

Любой хост, который не является CDN релизов GitHub:

* **Google Drive** — у меня подключение сейчас **выключено**. Включи его
  в настройках подключений, и я попробую забрать файл через коннектор.
* **Прикрепить файл в сообщение** — сработает, если он не слишком большой.
* **2 КБ вместо 293 МБ** — самый быстрый путь, см. `GET_UEXP.md`:
  ```bash
  python3 tools/slice_uexp.py --uexp Jeju_World.uexp --out houses_slice.zip
  ```
  В окне `242 123 897 … 242 128 055` лежат все 35 домов, этого хватает
  для проверки декодера и сборки патча.

## Почему я не могу просто «нажать скачать»

Песочница ходит в интернет по белому списку хостов. Разрешены
`github.com`, `api.github.com`, `codeload.github.com`, `registry.npmjs.org`,
`pypi.org`, `files.pythonhosted.org`. `release-assets.githubusercontent.com`
и `objects.githubusercontent.com` в него не входят — соединение режется
до HTTP, поэтому ни токен, ни публичность репозитория не помогают.

Публичный репозиторий, кстати, вижу и подтверждаю: `private: false`,
`visibility: public`. Спасибо, но проблема была не в этом.
