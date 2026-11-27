#!/usr/bin/env python3
"""
Сборка пак-мода BuildAnywhere в .pak (Windows, где есть игра).

Что делает:
  1. Проверяет, что рядом лежат: MotorTown-Windows.pak, Mappings.usmap, AES-ключ (.env)
  2. Распаковывает карту Jeju_World.umap из игры через repak (нужен repak в PATH)
  3. Патчит AreaSize через mappatch_houses (dotnet, см. mappatch_houses/)
  4. Собирает мод-папку MotorTown/Content/Maps/Jeju_World.umap (+ .uexp)
  5. Пакует в BuildAnywhere_P.pak через repak (или UnrealPak, если repak нет)

Использование:
  python build_pak.py --game-pak "C:/.../MotorTown-Windows.pak" --usmap Mappings.usmap --aes-key 0x... --size 20000

ВАЖНО: финальный .pak нельзя собрать в песочнице без файлов игры и AES-ключа.
Этот скрипт запускается на твоём Windows с установленной игрой.
"""
import argparse, os, shutil, subprocess, sys, pathlib

def run(cmd, **kw):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, **kw)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game-pak", required=True, help="путь к MotorTown-Windows.pak")
    ap.add_argument("--usmap", required=True, help="путь к Mappings.usmap (дамп через UE4SS)")
    ap.add_argument("--aes-key", required=True, help="AES-ключ пака, 0x... (AES Dumpster на MotorTown-Win64-Shipping.exe)")
    ap.add_argument("--size", type=int, default=20000, help="AreaSize в см, напр. 20000 = 200 м")
    ap.add_argument("--repak", default="repak", help="путь к repak")
    ap.add_argument("--dotnet", default="dotnet", help="путь к dotnet")
    args = ap.parse_args()

    root = pathlib.Path(__file__).resolve().parent.parent  # pak_mod/
    work = root / "work"
    work.mkdir(exist_ok=True)
    unpacked = work / "unpacked"
    mod_root = work / "BuildAnywhere_P"
    mod_maps = mod_root / "MotorTown" / "Content" / "Maps"
    mod_maps.mkdir(parents=True, exist_ok=True)

    if not shutil.which(args.repak):
        print(f"repak не найден в PATH ({args.repak}). Скачай: https://github.com/trumank/repak/releases")
        sys.exit(1)

    print("== 1. Распаковка карты из игры ==")
    # repak list сначала, чтобы найти точный путь карты
    out = subprocess.run([args.repak, "--aes-key", args.aes_key, "list", args.game_pak],
                         capture_output=True, text=True)
    print(out.stdout[:2000])
    candidates = [l.strip() for l in out.stdout.splitlines() if "Jeju_World" in l]
    print("Jeju_World в паке:", candidates)
    if not candidates:
        print("Карта Jeju_World не найдена в паке — проверь AES-ключ и версию игры.")
        sys.exit(1)

    run([args.repak, "--aes-key", args.aes_key, "unpack", "-o", str(unpacked), args.game_pak])

    # Ищем распакованную карту
    maps = list(unpacked.rglob("Jeju_World.umap"))
    if not maps:
        print("Jeju_World.umap не распаковался.")
        sys.exit(1)
    src_map = maps[0]
    print(f"Карта: {src_map}")

    print("== 2. Патч AreaSize (dotnet mappatch_houses) ==")
    proj = root / "mappatch_houses" / "mappatch_houses.csproj"
    out_map = mod_maps / "Jeju_World.umap"
    run([args.dotnet, "run", "--project", str(proj), "--",
         str(src_map), args.usmap, str(out_map), str(args.size)])
    # .uexp рядом с .umap нужен, если он есть у оригинала
    src_uexp = src_map.with_suffix(".uexp")
    if src_uexp.exists():
        shutil.copy2(src_uexp, mod_maps / "Jeju_World.uexp")
        print("Скопирован Jeju_World.uexp")

    print("== 3. Упаковка в .pak ==")
    pak_out = root / "BuildAnywhere_P.pak"
    # repak pack: repak pack <input_dir> <output.pak>  (без шифрования — мод-паки обычно не шифруются)
    run([args.repak, "pack", str(mod_root), str(pak_out)])
    print(f"\nГотово: {pak_out}")
    print("Установка: скопируй BuildAnywhere_P.pak в")
    print("  <Steam>/steamapps/common/Motor Town/MotorTown/Content/Paks/")
    print("  (или в .../Paks/~mods/ — зависит от версии игры, проверь по гайду economy mod)")
    print("ВАЖНО: мод даст cheat-flag, на чужом сервере не сработает без установки на сервере.")

if __name__ == "__main__":
    main()
