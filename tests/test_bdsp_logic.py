"""Prueba la lógica de DPBP con tablas falsas en memoria (sin bundles reales)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nuzrandom import settings as S  # noqa: E402
from nuzrandom.bdsp import randomizer as R  # noqa: E402
from nuzrandom.core import FileStore, Log  # noqa: E402


class FakeBundle:
    def __init__(self, trees):
        self.trees = trees
        self.dirty = set()

    def get(self, *names):
        for n in names:
            if n in self.trees:
                return self.trees[n]
        return None

    def touch(self, tree):
        for k, t in self.trees.items():
            if t is tree:
                self.dirty.add(k)

    def save(self):
        return b"bundle"


def fake():
    rng = random.Random(3)
    personal = []
    for i in range(0, 500):
        personal.append({"valid_flag": 1 if i else 0, "id": i, "monsno": i,
                         **{k: rng.randrange(20, 120) for k in R.STAT_KEYS},
                         "type1": rng.randrange(18), "type2": rng.randrange(18), "get_rate": 3,
                         "grow": 1, "tokusei1": 1, "tokusei2": 2, "tokusei3": 3,
                         "machine1": 0, "machine2": 0, "machine3": 0, "machine4": 0})
    evolve = [{"id": i, "ar": [5, 0, i + 1, 0, 0] if i % 3 == 1 else []} for i in range(500)]
    waza = [{"wazaNo": m, "isValid": 1, "type": m % 18, "power": m % 100, "hitPer": 100, "basePP": 10} for m in range(1, 468)]
    oboe = [{"id": i, "ar": [1, 33, 5, 45, 9, 52]} for i in range(500)]
    machines = [{"itemNo": 328 + k, "machineNo": k + 1, "wazaNo": 200 + k} for k in range(100)]
    pb = FakeBundle({"PersonalTable": {"m_Name": "PersonalTable", "Personal": personal},
                     "EvolveTable": {"Evolve": evolve}, "WazaTable": {"Waza": waza},
                     "WazaOboeTable": {"WazaOboe": oboe},
                     "ItemTable": {"WazaMachine": machines, "Item": [{"no": i, "price": 1000} for i in range(1, 700)]}})
    enc = {"table": [{"zoneID": z, "ground_mons": [{"maxlv": 5, "minlv": 3, "monsNo": 396 + (k % 3)} for k in range(12)],
                      "water_mons": [{"maxlv": 20, "minlv": 15, "monsNo": 129}]} for z in range(10)]}
    tpoke = [{"ID": t, **{f"P{n}MonsNo": (387 + t if n <= 2 else 0) for n in range(1, 7)},
              **{f"P{n}Level": 10 for n in range(1, 7)}, **{f"P{n}FormNo": 0 for n in range(1, 7)},
              **{f"P{n}Waza{w}": 0 for n in range(1, 7) for w in range(1, 5)}} for t in range(20)]
    ttypes = [{"TrainerID": 0, "LabelTrType": "TRTYPE_SCHOOLBOY"}, {"TrainerID": 1, "LabelTrType": "TRTYPE_LEADER1"}]
    tdata = [{"TypeID": 1 if t == 0 else 0, "AIBit": 7} for t in range(20)]
    shop = {"FS": [{"ItemNo": 4, "BadgeNum": 0, "ZoneID": -1}, {"ItemNo": 79, "BadgeNum": 3, "ZoneID": -1}],
            "FixedShop": [{"ShopID": 1, "ItemNo": 200 + k} for k in range(5)] + [{"ShopID": 2, "ItemNo": 330 + k} for k in range(4)]}
    mb = FakeBundle({"EncountTableD": enc, "ShopTable": shop,
                     "TrainerTable": {"TrainerType": ttypes, "TrainerData": tdata, "TrainerPoke": tpoke}})
    return pb, mb


def main():
    pb, mb = fake()
    r = R.BdspRandomizer.__new__(R.BdspRandomizer)
    cfg = S.nuzlocke_preset()
    cfg.types_mode = S.RANDOM
    cfg.learnset_mode = S.RANDOM
    cfg.tm_compat_mode = S.RANDOM
    r.st, r.cfg, r.rng, r.log = FileStore(Path(".")), cfg, random.Random(9), Log()
    r.pb, r.mb = pb, mb
    r.rel = {pb: "p", mb: "m"}
    r._load()
    r.run()
    zone = mb.trees["EncountTableD"]["table"]
    assert zone[0]["ground_mons"][0]["monsNo"] != 396
    assert zone[0]["ground_mons"][0]["monsNo"] == zone[0]["ground_mons"][3]["monsNo"]  # mapa por zona
    assert all(s["monsNo"] <= 493 for z in zone for s in z["ground_mons"])
    t0 = mb.trees["TrainerTable"]["TrainerPoke"][0]
    assert all(t0[f"P{n}MonsNo"] for n in range(1, 7)), t0
    assert len({t0[f"P{n}MonsNo"] for n in range(1, 7)}) == 6
    t1 = mb.trees["TrainerTable"]["TrainerPoke"][1]
    assert t1["P3MonsNo"] == 0, "un entrenador normal no debe crecer"
    items = {r["no"]: r["price"] for r in pb.trees["ItemTable"]["Item"]}
    assert items[17] == 250 and items[50] == 1 and items[92] == 1000
    fs = [r["ItemNo"] for r in mb.trees["ShopTable"]["FS"]]
    assert 77 in fs and 50 in fs
    fixed = mb.trees["ShopTable"]["FixedShop"]
    assert [r["ItemNo"] for r in fixed[:5]] != [200, 201, 202, 203, 204]
    assert all(328 <= r["ItemNo"] <= 427 for r in fixed[5:])
    assert pb.trees["EvolveTable"]["Evolve"][1]["ar"][0] == 4 and pb.trees["EvolveTable"]["Evolve"][1]["ar"][4] == 30
    assert set(r.st.changed) == {"p", "m"}
    print("BDSP lógica OK;", r.log.sections.keys())


if __name__ == "__main__":
    main()
