# BuildAnywhere — строительство за границами участка (Motor Town: Behind The Wheel)

Мод расширяет зону застройки купленных участков: можно строить далеко за
пределами ванильных 20×20 / 30×30 / 50×50 м.

---

## Что выяснено по твоим файлам (факты, не догадки)

Ассеты из `origin/main` (`4c17735`) разобраны: `House.uasset/.uexp`,
`Houses.uasset/.uexp`, `Jeju_World.umap/.ubulk` и `Mappings.usmap`.
Написал парсеры без dotnet/Cargo — `tools/usmap.py`, `tools/upak.py`,
`tools/decode_houses.py`, `tools/patch_world.py`.

**1. Схема (из твоего `Mappings.usmap`, версия 5, Zstd):**

| Класс | Свойства |
|---|---|
| `/Script/MotorTown.MTHouse` (родитель `Actor`) | **`AreaSize : Struct<Vector>`** (X/Y/Z = `Double`, см) — вот она, граница застройки; `MaxOutsidePlotDistance : Float` — допуск «снаружи участка»; `HousegKey : Name`; `HouseGuid : Struct<Guid>`; `Net_Buildings`, `Net_Modules`, `Net_Plan` |
| `/Script/MotorTown.MotorTownGameState` | `Houses : Array<Object>`, `Buildings : Array<Object>`, `AreaVolumes` |
| `/Game/DataAsset/Houses` (`MTHouseRow`) | `Name : Text`, `Cost : Int64`, `bAllowBuilding : Bool`, `PlotSize : Enum<EMTHousePlotSize>` |

`EMTHousePlotSize`: `Small = 0`, `Medium = 1`, `Large = 2`.

**2. Таблица участков полностью декодирована** (`tools/houses_table.json`,
39 строк). Размер участка — это класс, а не отдельные числа:

| Класс | Сколько | housingKey |
|---|---|---|
| Small | 11 | HousingTest_House0, FirstHouse, Oedo_01, BuildingTest, Aewol_01, Downtown_01, Hallim_01, PyoSun_01, SungSan_01, GwangjinTown_01, Daejin_01 |
| Medium | 12 | Downtown_02, Gapa_01, Gapa_02, JoCheon_01, SeoGuiPo_WestTown_01, SinChang_01, GwangjinTown_02, Biyang_01, Sanho_02, Dongsan_01, Ara_01, Baram_01 |
| Large | 15 | Gujwa_ContainerHouse, GimNyungBeach_01, Gujwa_01, CheonJin_01, CheonJin_02, Downtown_03, SeoGuiPo_WestTown_02, Gwangjin_01, Biyang_02, Sanho_01, Obo_01, Obo_02, Gwangjin_02, Gaon_01 |

Твои два участка — `CheonJin_02` и `Gujwa_01`, оба **Large**.

**3. Где хранятся реальные значения AreaSize — и почему их не было видно.**
`Jeju_World.umap` — это только заголовок (13 918 730 байт, ровно `section_six`).
Все данные объектов лежат в **`Jeju_World.uexp`** (306 853 978 байт ≈ 293 МБ),
которого в загрузке не было. Поэтому поиск строки `AreaSize` в `.umap` дал 0:
там 78 756 записей экспорта, но ни одного байта свойств. В мире 35 экземпляров
`House_C`, их данные — в диапазоне смещений 242 123 961 … 242 128 055 внутри `.uexp`.

**4. В сейве (`Island.sav.txt`) AreaSize нет** — это подтверждено, поле живёт
только в акторе на карте. Правка сейва эту задачу не решает.

---

## Что нужно от тебя (один файл)

`Jeju_World.uexp` из распакованного пака игры (≈293 МБ). Как достать:

1. **Рабочий путь — git** (релизы GitHub из песочницы недоступны):
`UPLOAD_UEXP.md`, две команды `git add` + `git push`.

**Быстрый вариант — 2 КБ вместо 293 МБ:** см. `GET_UEXP.md`, там готовый скрипт
`tools/slice_uexp.py`, который вырезает окно со всеми 35 домами.

**Проще всего** — UE4SS + FModel: открыть пак игры, найти
   `/Game/Maps/Jeju/Jeju_World`, сделать Save/Export — FModel положит
   `.uasset/.uexp/.ubulk`. Нужен AES-ключ (AES Dumpster по `MotorTown-Win64-Shipping.exe`).
2. Либо `repak unpack` / `UnrealPak` по инструкции из `WHAT_TO_UPLOAD.md`.
3. Залей `.uexp` на GitHub Release (до 2 ГБ) или в Google Drive — Drive у меня
   сейчас **выключен**, включи его в настройках подключений, если хочешь через него.

После загрузки я прогоню `tools/patch_world.py`, проверю все 35 домов и соберу
готовый `BuildAnywhere_P.pak`.

---

## Вариант без файлов вообще: Lua-мод (работает уже сейчас)

`ue4ss/Mods/BuildAnywhere/Scripts/main.lua` — ставится как обычный UE4SS-мод,
без pak и без AES-ключа. Правит `AreaSize` у домов в памяти.

* **F8** — расширить застройку (по умолчанию 200×200 м, `CONFIG.bigSize`)
* **F9** — вернуть 50×50 м
* **F7** — отчёт: какие дома найдены, их `HousegKey`, владелец, текущий AreaSize
* консоль `~`: `buildanywhere 20000`, `buildanywhere_reset`, `buildanywhere_info`

Мод читает дома из `MotorTownGameState.Houses` (поле подтверждено в usmap),
а не из придуманного API, и меняет `AreaSize` вместе с `MaxOutsidePlotDistance`.
Новые дома ловятся через `NotifyOnNewObject` на `/Script/MotorTown.MTHouse`
и `/Game/Objects/Housing/House.House_C`.

**Установка:** папку `BuildAnywhere` из `ue4ss/Mods/` положить в
`.../MotorTown/Binaries/Win64/ue4ss/Mods/`, в `mods.txt` добавить строку
`BuildAnywhere : 1`, запустить игру.

### Ограничения
* **Сервер решает всё.** Границу проверяет серверная логика
  (`MTHousingPlanningComponent`), так что мод работает в соло и на своём
  выделенном сервере; на чужом сервере серверные дома не изменить.
* Флаг «читы» игра может выставить — на лидерборды/ачивки это влияет.
* После обновления игры мод и `.pak` могут потребовать пересборки.

---

## Pak-вариант (когда будет `.uexp`)

```bash
cd /home/user/mt_save
python3 tools/patch_world.py --umap Jeju_World.umap --uexp Jeju_World.uexp \
        --usmap Mappings.usmap --size 20000 --out patched/
# затем упаковать patched/Jeju_World.umap + patched/Jeju_World.uexp
# в MotorTown/Content/Maps/ и собрать BuildAnywhere_P.pak (repak или UnrealPak)
```

`tools/patch_world.py --dry-run` покажет все 35 домов и их текущие AreaSize,
ничего не записывая. Патч меняет только 24 байта вектора (и 4 байта допуска)
на дом — размеры не меняются, смещения остаются валидными.

Старые вспомогательные файлы (`pak_mod/mappatch_houses/Program.cs`,
`pak_mod/scripts/build_pak.py`) оставлены на случай, если захочешь патчить
через UAssetAPI на Windows; основной путь теперь — `tools/patch_world.py`.
