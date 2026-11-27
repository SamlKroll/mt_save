# Что выгрузить через FModel для сборки пак-мода «вся карта — мой участок»

Цель мода: `AreaSize` у дома = вся карта (например 2000×2000 м и больше),
чтобы build-режим разрешал ставить здания в любой точке, как будто это твой участок.

## 1. Файлы из FModel (главное)

Открой MotorTown в FModel (AES-ключ уже введён в FModel — мне ключ не нужен,
если ты выгружаешь готовые ассеты). В поиске FModel вбей и выгрузи (ПКМ → Extract / Save):

1. **Jeju_World.umap + Jeju_World.uexp** — главная карта, там акторы домов с `AreaSize`
   - Ищи: `Jeju_World`
   - Путь примерно: `MotorTown/Content/Maps/Jeju_World.umap`
   - Если FModel покажет несколько частей (World Partition cells) — выгрузи все,
     где в имени есть `Jeju` и `House`, и напиши, какие именно нашёл.

2. **Houses.uasset + Houses.uexp** (если есть) — DataAsset участков
   - Ищи: `DataAsset/Houses`
   - Путь: `MotorTown/Content/DataAsset/Houses.uasset`

3. **House.uasset + House.uexp** — блюпринт дома AMTHouse
   - Ищи: `Objects/Housing/House`
   - Путь: `MotorTown/Content/Objects/Housing/House.uasset`

Если какого-то файла нет в FModel — просто напиши, что не нашёл, и что нашёл вместо него
(скриншот списка файлов из папки тоже подойдёт).

## 2. Mappings.usmap (не из FModel, а из UE4SS)

1. Поставь UE4SS Experimental zdev в `MotorTown/Binaries/Win64/`
2. В `ue4ss/UE4SS-settings.ini`: EngineMajorVersion=5, EngineMinorVersion=5
3. Запусти игру, в консоли UE4SS: Dumpers → Dump usmap
4. Файл `Mappings.usmap` появится в папке `ue4ss/` — выгрузи его тоже.

## 3. Информация (напиши в чат)

- Версия игры: ПКМ по `MotorTown-Win64-Shipping.exe` → Свойства → Подробно → Версия продукта (например 5.5.4.0)
- Кому расширять: всем домам / только твоим `CheonJin_02` + `Gujwa_01` / только одному
- Размер: вся карта = предлагаю `AreaSize = 2000000 x 2000000 см` (20×20 км, с запасом на всю Jeju).
  Если хочешь другой — напиши свой в метрах.
- Соло или свой дедик? (на чужом сервере пак на клиенте не сработает)

## 4. Куда заливать

Как и в прошлый раз: GitHub → твой репозиторий `mt_save` → ветка **main** →
Add file → Upload files → перетащи файлы → Commit.
GitHub не даёт >100 МБ на файл: если `.umap` больше — заархивируй в `.zip` и залей zip,
я распакую. Напиши мне «залил», я заберу файлы с `origin/main` и соберу пак.

## Что я сделаю после загрузки
1. Пропатчу `AreaSize` в `Jeju_World.umap` через UAssetAPI (mappatch_houses)
2. Проверю `Houses` / `House` на лимит зданий — если лимит в ассете, подниму и его
3. Соберу `BuildAnywhere_P.pak` через repak
4. Дам инструкцию: куда кинуть пак (`MotorTown/Content/Paks/`)

⚠️ Мод = cheat-flag. На чужом сервере без мода на сервере здания вне участка не сохранятся.
