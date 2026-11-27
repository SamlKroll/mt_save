#!/usr/bin/env python3
"""
Анализ расшифрованного MotorTown Island.world (Island.sav.txt, JSON, version=8)
Вопрос: есть ли в сейве поле площади строительства / размера участка / лимита зданий?
Ответ: нет. См. вывод ниже.
"""
import json, pathlib, collections, re, sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "Island.sav.txt")
data = json.loads(p.read_text(encoding="utf-8"))
world = data["world"]
print(f"version={data.get('version')} day={world.get('day')} worldKey={world.get('worldKey')}")

housings = world.get("housings", {})
print(f"\nhousings: {len(housings)} записей, ключи полей: {sorted({k for v in housings.values() for k in v})}")
print("  -> НЕТ size/area/limit/plot/extent. Только: housingKey, owner*, rentLeftTimeSeconds, buildAccess")

buildings = world.get("buildings", [])
print(f"\nbuildings: {len(buildings)} записей, ключи полей: {sorted({k for b in buildings for k in b})}")
print("  -> НЕТ size/scale/limit. Только: buildingKey, housingKey, location, rotation, owner*, guid...")

print(f"\nhousingPlans: {world.get('housingPlans')}")

text = p.read_text(encoding="utf-8")
for kw in ["size", "area", "limit", "plot", "extent", "scale", "width", "height", "bound"]:
    print(f"  keyword '{kw}': {len(re.findall(kw, text, re.I))} вхождений")

print("\nУчастки SAML_KROLL:")
for k, v in housings.items():
    if v.get("ownerName") == "SAML_KROLL":
        hk = v["housingKey"]
        bs = [b for b in buildings if b.get("housingKey") == hk]
        xs = [b["location"]["x"] for b in bs]; ys = [b["location"]["y"] for b in bs]
        print(f"  {hk}: зданий={len(bs)}, bbox={(max(xs)-min(xs))/100:.1f} x {(max(ys)-min(ys))/100:.1f} м "
              f"(координаты UE в см), здания={[b['buildingKey'] for b in bs]}")

print("\nВывод: площадь участка задаётся housingKey в данных игры (уровень/DataAsset),")
print("а не числом в сейве. Увеличить её правкой JSON нельзя — поля просто нет.")
print("Можно только: сменить housingKey на другой участок (с переносом зданий на его")
print("координаты и сменой владельца) — это уже не 'увеличение', а подмена участка,")
print("с cheat-flag и риском удаления зданий вне границ нового участка.")
