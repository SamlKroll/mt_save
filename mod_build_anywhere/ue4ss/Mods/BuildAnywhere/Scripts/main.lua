-- BuildAnywhere — Motor Town: Behind The Wheel (UE 5.5, UE4SS Lua)
--
-- Что делает: увеличивает площадь застройки у домов игрока, чтобы строить далеко
-- за границами участка 20x20 / 30x30 / 50x50 м.
--
-- На чём основано (проверено по Mappings.usmap из твоей же сборки игры):
--   /Script/MotorTown.MTHouse                     (родитель: Actor)
--     AreaSize               : FVector (X/Y/Z = Double, сантиметры)  <-- вот она, граница застройки
--     MaxOutsidePlotDistance : Float                                <-- допуск "снаружи участка"
--   /Script/MotorTown.MotorTownGameState
--     Houses                 : Array<Object>                        <-- все дома мира
--   /Game/DataAsset/Houses   (MTHouseRow: Name, Cost, bAllowBuilding, PlotSize)
--     PlotSize               : Small=0 / Medium=1 / Large=2
--
-- Установка: см. ../../README.md
-- Клавиши:
--   F8  — расширить застройку (по умолчанию 200 x 200 м)
--   F9  — вернуть 50 x 50 м (потолок ванильного Large)
--   F7  — отчёт: какие дома найдены, их housingKey, текущий AreaSize, класс участка
-- Консоль (~):
--   buildanywhere 20000          -- размер в см
--   buildanywhere_reset
--   buildanywhere_info

local UEHelpers = require("UEHelpers")

-- ===================== настройки =====================
local CONFIG = {
    -- 20000 см = 200 м. Меняй под себя.
    bigSize = { X = 20000, Y = 20000, Z = 5000 },
    -- "mine" = только дома локального игрока, "all" = все дома мира.
    -- В соло и на своём сервере разницы нет. На чужом сервере оставь "mine".
    mode = "mine",
    -- Дополнительный допуск за границей участка (см). Игра разрешает ставить
    -- объекты, свисающие за границу, на эту величину.
    outsideDistance = 20000.0,
    -- Применять автоматически к каждому новому дому (хук на спавн).
    autoApply = true,
}

local HOUSES_DATA_ASSET = "/Game/DataAsset/Houses.Houses"
local HOUSE_CLASS = "/Game/Objects/Housing/House.House_C"
local HOUSE_NATIVE_CLASS = "/Script/MotorTown.MTHouse"

local plotLabels = { [0] = "Small", [1] = "Medium", [2] = "Large" }

-- ===================== утилиты =====================
local function log(msg, ...)
    if select("#", ...) > 0 then
        msg = string.format(msg, ...)
    end
    print("[BuildAnywhere] " .. msg)
end

local function safe(fn, ...)
    local ok, err = pcall(fn, ...)
    if not ok then
        log("ошибка: %s", tostring(err))
    end
    return ok
end

local function isValid(obj)
    return obj and obj.IsValid and obj:IsValid()
end

--- GameState (в нём лежит Houses: TArray<AMTHouse*>)
local function getGameState()
    local ok, gs = pcall(function()
        return FindFirstOf("MotorTownGameState")
    end)
    if ok and isValid(gs) then
        return gs
    end
    ok, gs = pcall(function()
        local state = UEHelpers:GetGameStateBase()
        if isValid(state) then return state end
        return nil
    end)
    if ok then return gs end
    return nil
end

local function getHouses()
    local gs = getGameState()
    if not isValid(gs) then
        return nil, "GameState не найден (ты в меню?). Зайди в мир и попробуй снова."
    end
    local ok, houses = pcall(function() return gs.Houses end)
    if not ok or houses == nil then
        return nil, "у GameState нет поля Houses"
    end
    local out = {}
    -- UE4SS: TArray приходит как таблица с 1-based индексами
    local ok2, n = pcall(function() return #houses end)
    if not ok2 then return nil, "Houses не читается как массив" end
    for i = 1, n do
        local h = houses[i]
        if isValid(h) then out[#out + 1] = h end
    end
    return out
end

--- локальный игрок (для режима "mine")
local function getLocalOwnerName()
    local ok, name = pcall(function()
        local pc = UEHelpers.GetPlayerController()
        if not isValid(pc) then return nil end
        local ps = pc.PlayerState
        if not isValid(ps) then return nil end
        return ps.PlayerName:ToString()
    end)
    if ok then return name end
    return nil
end

local function houseKey(house)
    local ok, key = pcall(function() return house.HousegKey:ToString() end)
    if ok then return key end
    return "?"
end

local function houseOwner(house)
    local ok, owner = pcall(function() return house.Net_OwnerName:ToString() end)
    if ok then return owner end
    return ""
end

local function areaSize(house)
    local ok, v = pcall(function()
        local a = house.AreaSize
        return { X = a.X, Y = a.Y, Z = a.Z }
    end)
    if ok then return v end
    return nil
end

--- Правка AreaSize. FVector в UE5 с LargeWorldCoordinates — из Double,
--- поэтому читаем текущий вектор, меняем компоненты и присваиваем обратно.
local function setArea(house, size)
    local v = house.AreaSize
    v.X = size.X
    v.Y = size.Y
    v.Z = size.Z
    house.AreaSize = v
    safe(function()
        house.MaxOutsidePlotDistance = CONFIG.outsideDistance
    end)
end

local function isMine(house, me)
    if CONFIG.mode == "all" or me == nil then return true end
    local owner = houseOwner(house)
    return owner == me or owner == ""
end

-- ===================== основная работа =====================
local function applyToAll(size, label)
    local houses, err = getHouses()
    if not houses then
        log(err)
        return 0
    end
    local me = CONFIG.mode == "mine" and getLocalOwnerName() or nil
    local changed, skipped = 0, 0
    for _, house in ipairs(houses) do
        if isMine(house, me) then
            local ok = safe(setArea, house, size)
            if ok then changed = changed + 1 end
        else
            skipped = skipped + 1
        end
    end
    log("%s: домов изменено %d, пропущено %d, размер %.0f x %.0f м",
        label, changed, skipped, size.X / 100, size.Y / 100)
    if changed == 0 then
        log("Подсказка: дома принадлежат серверу — в соло/на своём сервере должно сработать.")
    end
    return changed
end

local function applyToHouse(house)
    if not isValid(house) then return end
    local me = CONFIG.mode == "mine" and getLocalOwnerName() or nil
    if isMine(house, me) then
        safe(setArea, house, CONFIG.bigSize)
        log("новый дом %s: AreaSize -> %.0f x %.0f м", houseKey(house),
            CONFIG.bigSize.X / 100, CONFIG.bigSize.Y / 100)
    end
end

local function printInfo()
    local houses, err = getHouses()
    if not houses then
        log(err)
        return
    end
    local me = getLocalOwnerName()
    log("домов в мире: %d, ты: %s, режим: %s", #houses, tostring(me), CONFIG.mode)
    for _, house in ipairs(houses) do
        local a = areaSize(house)
        log("  %-22s owner=%-18s area=%s x %s x %s",
            houseKey(house), houseOwner(house),
            a and string.format("%.0f", a.X / 100) or "?",
            a and string.format("%.0f", a.Y / 100) or "?",
            a and string.format("%.0f", a.Z / 100) or "?")
    end
end

-- ===================== входные точки =====================
local function onBig()
    log("F8: расширяю застройку...")
    applyToAll(CONFIG.bigSize, "BIG")
end

local function onReset()
    log("F9: возвращаю 50 x 50 м...")
    applyToAll({ X = 5000, Y = 5000, Z = 5000 }, "RESET")
end

RegisterKeyBind(Key.F8, {}, onBig)
RegisterKeyBind(Key.F9, {}, onReset)
RegisterKeyBind(Key.F7, {}, printInfo)

RegisterConsoleCommandHandler("buildanywhere", function(_, parts)
    local cm = tonumber(parts[1])
    if cm and cm > 0 then
        applyToAll({ X = cm, Y = cm, Z = CONFIG.bigSize.Z }, "CUSTOM")
    else
        onBig()
    end
    return true
end)

RegisterConsoleCommandHandler("buildanywhere_reset", function()
    onReset()
    return true
end)

RegisterConsoleCommandHandler("buildanywhere_info", function()
    printInfo()
    return true
end)

-- Каждый новый дом (в т.ч. только что купленный) сразу получает большой AreaSize.
if CONFIG.autoApply then
    safe(function()
        NotifyOnNewObject(HOUSE_NATIVE_CLASS, function(house)
            applyToHouse(house)
        end)
        NotifyOnNewObject(HOUSE_CLASS, function(house)
            applyToHouse(house)
        end)
    end)
end

-- После загрузки мира дома уже стоят — применяем один раз с задержкой.
local appliedOnce = false
safe(function()
    RegisterHook("/Script/Engine.PlayerController:ServerAcknowledgePossession", function()
        if appliedOnce then return end
        appliedOnce = true
        ExecuteWithDelay(5000, function()
            applyToAll(CONFIG.bigSize, "AUTO")
        end)
    end)
end)

log("загружен. F8 = расширить (%.0f м), F9 = вернуть 50 м, F7 = отчёт, консоль: buildanywhere [см]",
    CONFIG.bigSize.X / 100)
