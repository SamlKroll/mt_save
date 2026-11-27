// mappatch_houses: патчит persistent world map Motor Town (Jeju_World.umap)
// и увеличивает AreaSize у всех акторов AMTHouse (/Game/Objects/Housing/House.House_C).
//
// Зачем: AreaSize живёт НЕ в сейве и НЕ в DataAsset Houses, а в акторе дома на карте.
// Поэтому пак-мод должен править именно карту, а не только DataAsset.
//
// Использование (на Windows, где установлена игра):
//   mappatch_houses <Jeju_World.umap> <Mappings.usmap> <out.umap> [size_cm]
//   size_cm по умолчанию 20000  (= 200 м x 200 м)
//
// Сборка: dotnet build -c Release  (нужен .NET 8 SDK + UAssetAPI, см. README)
// Результат out.umap кладётся обратно в мод-папку как:
//   MotorTown/Content/Maps/Jeju_World.umap  (+ .uexp если есть)
// и пакуется в *_P.pak через repak / UnrealPak (см. scripts/build_pak.py).

using System;
using System.Linq;
using UAssetAPI;
using UAssetAPI.ExportTypes;
using UAssetAPI.PropertyTypes.Objects;
using UAssetAPI.PropertyTypes.Structs;
using UAssetAPI.UnrealTypes;
using UAssetAPI.Unversioned;

static class P
{
    static void Main(string[] args)
    {
        if (args.Length < 3)
        {
            Console.WriteLine("usage: mappatch_houses <map.umap> <mappings.usmap> <out.umap> [size_cm]");
            return;
        }
        string mapPath = args[0], usmapPath = args[1], outPath = args[2];
        double size = args.Length > 3 ? double.Parse(args[3]) : 20000.0;

        var usmap = new USMAP(usmapPath);
        var asset = new UAsset(mapPath, EngineVersion.VER_UE5_5, usmap);
        int patched = 0;

        foreach (var exp in asset.Exports.OfType<NormalExport>())
        {
            // Ищем экспорты-акторы домов: класс House_C / AMTHouse
            string cls = "";
            try
            {
                if (exp.ClassIndex.IsImport()) cls = exp.ClassIndex.ToImport(asset).ObjectName.ToString();
                else if (exp.ClassIndex.IsExport()) cls = exp.ClassIndex.ToExport(asset).ObjectName.ToString();
            }
            catch { }
            if (!(cls.Contains("House") || exp.ObjectName.ToString().Contains("House")))
                continue;

            var areaProp = exp.Data.OfType<VectorPropertyData>()
                .FirstOrDefault(p => p.Name.ToString() == "AreaSize");
            if (areaProp == null)
                continue;

            Console.WriteLine($"  {exp.ObjectName}: AreaSize {areaProp.Value} -> ({size},{size},5000)");
            areaProp.Value = new FVector(size, size, 5000);
            patched++;
        }

        Console.WriteLine($"Patched {patched} house actors. Writing {outPath} ...");
        if (patched == 0)
            Console.WriteLine("WARNING: домов с AreaSize не найдено. Проверь, что это Jeju_World.umap и usmap от той же версии игры.");
        asset.Write(outPath);
    }
}
