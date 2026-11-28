#!/usr/bin/env python3
"""Dump the housing/building-related part of Mappings.usmap to JSON.

Everything the mod needs is in here, so the Windows side never needs zstandard:
usmap.py falls back to tools/schema.json when it cannot decompress the .usmap.

    python3 tools/dump_schema.py --usmap Mappings.usmap --out tools/schema.json
"""
import argparse
import collections
import json
import sys

sys.path.insert(0, "tools")
import usmap

# Everything reachable from the classes the mod touches.
ROOTS = [
    "MTHouse", "MTHouseRow", "MTHouseForSale", "MTBuilding", "MTBuildingRow",
    "MTBuildingStep", "MTBuildingConstruction", "MTNetBuildingConstruction",
    "MTNetBuildingConstructionMaterial", "MTHousingPlanningComponent",
    "DataTable", "TableRowBase", "Vector", "Guid", "MTItemInventory",
    "MTTextByTexts", "MTNetHousingModuleArray", "MTNetHousingPlanArray",
    "MTNetHousingModule", "MTNetHousingPlanModule", "MTBuildingAccessSettings",
    "MTBuildingColorOverride", "MTBuildingItemInventory", "MTBuildingDepot",
    "MTBuildingColorSlot", "MTBuildingMaterialNet", "MTSaveGameHouse",
    "MotorTownGameState", "MTLocalHousingPlanState",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--usmap", default="Mappings.usmap")
    ap.add_argument("--out", default="tools/schema.json")
    args = ap.parse_args()

    u = usmap.load(args.usmap)
    structs = {}
    queue = collections.deque(ROOTS)
    seen = set()

    def add_type(t):
        if not t:
            return
        kind = t[0]
        if kind == "Struct":
            queue.append(t[1])
        elif kind == "Enum":
            add_type(t[1])
        elif kind in ("Array", "Set", "Optional"):
            add_type(t[1])
        elif kind == "Map":
            add_type(t[1])
            add_type(t[2])

    while queue:
        name = queue.popleft()
        if not name or name in seen:
            continue
        seen.add(name)
        s = u.get(name)
        if s is None:
            continue
        structs[name] = {
            "super": s.super,
            "props": [{"index": p.index, "name": p.name, "type": list(p.type)} for p in s.props],
        }
        queue.append(s.super)
        for p in s.props:
            add_type(p.type)

    enums = {k: [[v, n] for v, n in vals] for k, vals in u.enums.items()}

    out = {
        "source": args.usmap,
        "usmap_version": u.version,
        "name_count": len(u.names),
        "struct_count_total": len(u.structs),
        "structs": structs,
        "enums": enums,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f"{args.out}: {len(structs)} structs, {len(enums)} enums")
    for n in ("MTHouse", "MTBuildingRow"):
        if n in structs:
            print(f"  {n}: {len(structs[n]['props'])} props")


if __name__ == "__main__":
    main()
