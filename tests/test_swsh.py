"""Prueba de extremo a extremo con un romfs falso: python -I tests/test_swsh.py <carpeta_temporal>"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import make_fake_swsh  # noqa: E402
from nuzrandom import engine, settings as S  # noqa: E402
from nuzrandom.core import LEGENDARIES  # noqa: E402
from nuzrandom.swsh import items as IT  # noqa: E402
from nuzrandom.swsh.formats import FB, Gfpak, fnv1a64  # noqa: E402


def species_in_enc(data):
    fb = FB(bytearray(data))
    out = []
    for z in fb.tables(fb.root(), 1):
        for sub in fb.tables(z, 1):
            for sl in fb.tables(sub, 2):
                out.append(fb.get(sl, 1, "I"))
    return out


def price(data, iid):
    rec_off = struct.unpack_from("<I", data, 0x40)[0]
    r = struct.unpack_from("<H", data, 0x44 + iid * 2)[0]
    return struct.unpack_from("<I", data, rec_off + r * 48)[0]


def main(tmp: Path):
    make_fake_swsh.main(tmp)
    romfs = tmp / "romfs"
    orig_pak = Gfpak((romfs / "bin/archive/field/resident/data_table.gfpak").read_bytes())
    assert Gfpak(orig_pak.build()).get("encount_k.bin") == orig_pak.get("encount_k.bin")

    cfg = S.nuzlocke_preset()
    cfg.seed = "prueba"
    cfg.types_mode = cfg.abilities_mode = S.RANDOM
    cfg.stats_mode = "redistribuir"
    cfg.learnset_mode = cfg.tm_moves_mode = S.RANDOM
    cfg.tm_compat_mode = S.RANDOM
    cfg.move_data_random = True
    cfg.wild_level_percent = 20
    cfg.mart_extra_items = "1, 2"
    out = tmp / "salida"
    res = engine.run(str(romfs), "Espada", cfg, str(out), None, emit=lambda m: None)
    mod = out / "NuzRandom" / "romfs"
    print("archivos:", res["files"])

    # originales intactos
    assert Gfpak((romfs / "bin/archive/field/resident/data_table.gfpak").read_bytes()).get("encount_k.bin") \
        == orig_pak.get("encount_k.bin")

    # --- salvajes
    pak = Gfpak((mod / "bin/archive/field/resident/data_table.gfpak").read_bytes())
    before = species_in_enc(orig_pak.get("encount_k.bin"))
    after = species_in_enc(pak.get("encount_k.bin"))
    assert len(before) == len(after) and before != after
    assert all(s % 7 for s in after), "usó especies fuera del juego"
    assert not set(after) & LEGENDARIES
    sym_before = set(species_in_enc(orig_pak.get("encount_symbol_k.bin")) + species_in_enc(orig_pak.get("encount_symbol_t.bin")))
    assert set(species_in_enc(pak.get("encount_symbol_k.bin"))) <= sym_before

    # --- starters
    ap = FB(bytearray((mod / "bin/script_event_data/add_poke.bin").read_bytes()))
    st = [ap.get(t, 9, "I") for t in ap.root_tables()]
    assert st[:3] != [810, 813, 816] and st[4] == 150

    # --- jefes de 6, el resto igual
    td = (mod / "bin/trainer/trainer_data/trainer_data_032.bin").read_bytes()
    tp = (mod / "bin/trainer/trainer_poke/trainer_poke_032.bin").read_bytes()
    assert td[3] == 6 and len(tp) == 6 * 0x20, "el jefe 32 no tiene 6"
    species = [struct.unpack_from("<H", tp, s * 0x20 + 0x0C)[0] for s in range(6)]
    assert len(set(species)) == 6, f"especies repetidas en el jefe: {species}"
    assert struct.unpack_from("<I", td, 0x0C)[0] == 0xFFFFFFFF  # IA máxima de jefe
    td10 = (mod / "bin/trainer/trainer_data/trainer_data_010.bin").read_bytes()
    tp10 = (mod / "bin/trainer/trainer_poke/trainer_poke_010.bin").read_bytes()
    assert td10[3] == 3 and len(tp10) == 3 * 0x20, "un entrenador normal cambió de tamaño"
    td4 = romfs / "bin/trainer/trainer_data/trainer_data_004.bin"
    assert not (mod / "bin/trainer/trainer_data/trainer_data_004.bin").exists() or \
        (mod / "bin/trainer/trainer_data/trainer_data_004.bin").read_bytes()[3] == td4.read_bytes()[3]

    # --- evoluciones
    assert not (mod / "bin/pml/evolution/evo_001.bin").exists()  # nivel 16: no cambia
    evo1 = (romfs / "bin/pml/evolution/evo_001.bin").read_bytes()
    m, _a, _t = struct.unpack_from("<HHH", evo1, 0)
    assert m == 4 and evo1[7] == 16
    evo4 = (mod / "bin/pml/evolution/evo_004.bin").read_bytes()   # intercambio -> nivel
    assert struct.unpack_from("<H", evo4, 0)[0] == 4 and evo4[7] == 30, (struct.unpack_from("<H", evo4, 0), evo4[7])
    evo25 = (mod / "bin/pml/evolution/evo_025.bin").read_bytes()  # método 4 nivel 50 -> tope 36
    assert evo25[7] == 36, evo25[7]

    # --- precios y tienda
    it0 = (romfs / IT.ITEM).read_bytes()
    it1 = (mod / IT.ITEM).read_bytes()
    assert price(it1, 17) == round(price(it0, 17) * 0.25)
    assert price(it1, 92) == price(it0, 92), "la Pepita no debía abaratarse"
    assert price(it1, IT.RARE_CANDY) == 1
    shop = bytearray((mod / IT.SHOP).read_bytes())
    invs = IT.shop_inventories(FB(shop))
    main_invs = [v for _a, _p, v in invs if 4 in v or 17 in v]
    assert len(main_invs) == 5 and all(v[:3] == [IT.MAX_REPEL, IT.RARE_CANDY, 1] and 2 in v for v in main_invs), main_invs
    tiers = [v for v in main_invs if len(v) > 6]
    assert main_invs[-1] == [IT.MAX_REPEL, IT.RARE_CANDY, 1, 4, 17, 2, 3]
    assert [IT.MAX_REPEL, IT.RARE_CANDY, 1, 2, 17, 18, 19] in main_invs, "la primera tienda (sin Poké Balls) se tocó"
    sec = [v for _a, _p, v in invs if v and v[0] not in (IT.MAX_REPEL,) and len(v) == 5][0]
    assert sec != [213, 214, 215, 216, 217]
    tm = [v for _a, _p, v in invs if len(v) == 4 and IT.MAX_REPEL not in v][0]
    assert all(x in IT.TM_ITEMS for x in tm) and tm != [328, 329, 330, 331]

    # --- objetos del suelo (clave protegida, vacío intacto)
    p0 = Gfpak((romfs / IT.PLACEMENT).read_bytes())
    p1 = Gfpak((mod / IT.PLACEMENT).read_bytes())
    z0, z1 = p0.get_index(0), p1.get_index(0)
    assert z0 != z1
    assert fnv1a64("item_1100").to_bytes(8, "little") in z1, "se movió un objeto clave del suelo"
    assert fnv1a64("").to_bytes(8, "little") in z1

    # --- regalos NPC: por defecto no se tocan
    assert not (mod / "bin/script/amx/main_event_0180.amx").exists(), "se tocó un regalo con la opción apagada"

    # --- reproducible
    engine.run(str(romfs), "Espada", cfg, str(tmp / "salida2"), None, emit=lambda m: None)
    for rel in ("bin/archive/field/resident/data_table.gfpak", IT.SHOP, IT.PLACEMENT, IT.ITEM):
        assert (mod / rel).read_bytes() == (tmp / "salida2/NuzRandom/romfs" / rel).read_bytes(), rel
    # --- regalos NPC activados: las Poké Balls y objetos clave se respetan
    cfg.gift_items_random = True
    engine.run(str(romfs), "Espada", cfg, str(tmp / "salida3"), None, emit=lambda m: None)
    mod3 = tmp / "salida3/NuzRandom/romfs"
    assert not (mod3 / "bin/script/amx/main_event_0180.amx").exists(), "se cambiaron Poké Balls regaladas"
    assert not (mod3 / "bin/script/amx/main_event_0300.amx").exists(), "se tocó un objeto clave regalado"
    a0 = (romfs / "bin/script/amx/main_event_0340.amx").read_bytes()
    cells, _b, _c = IT._amx_decode((mod3 / "bin/script/amx/main_event_0340.amx").read_bytes())
    assert cells[6060] & 0xFFFFFFFF == 0xBC and cells[6060] >> 32 != 367
    assert IT._amx_decode(a0)[0][:6060] == cells[:6060] and IT._amx_decode(a0)[0][6061:] == cells[6061:]

    # --- combate oculto: copia el módulo al exefs y escribe config.toml
    import tomllib
    from nuzrandom.swsh import runtime as RT
    cfg.hidden_battle = True
    cfg.exlaunch_dir = str(tmp / "no_existe")
    try:
        engine.run(str(romfs), "Espada", cfg, str(tmp / "salida4"), None, emit=lambda m: None)
        raise AssertionError("debía avisar de que falta el módulo")
    except RuntimeError as e:
        assert "PokeFeur" in str(e)
    assert not (tmp / "salida4").exists(), "no debía generar nada sin el módulo"
    pf = tmp / "PokeFeur" / "assets" / "exlaunch" / "0100ABF008968000"
    pf.mkdir(parents=True)
    (pf / "subsdk9_stable").write_bytes(b"SUBSDK")
    (pf / "main.npdm_stable").write_bytes(b"NPDM")
    cfg.exlaunch_dir = str(tmp / "PokeFeur")
    cfg.hidden_battle_mode = "zona"
    engine.run(str(romfs), "Espada", cfg, str(tmp / "salida4"), None, emit=lambda m: None)
    mod4 = tmp / "salida4" / "NuzRandom"
    assert (mod4 / "exefs" / "subsdk9").read_bytes() == b"SUBSDK"
    assert (mod4 / "exefs" / "main.npdm").read_bytes() == b"NPDM"
    conf = tomllib.loads((tmp / "salida4" / "sdcard" / RT.CONFIG_REL).read_text(encoding="utf-8"))
    rz = conf["randomizer"]
    assert rz["active"] and rz["visible_mode"] == "vanilla" and rz["battle_mode"] == "zone"
    assert rz["battle_pool"] and not set(rz["battle_pool"]) & LEGENDARIES
    assert conf["exp_share"]["enabled"] and not conf["exp_level_cap"]["active"] and not conf["early_bike"]["active"]
    assert 0 <= rz["seed"] < 2**63

    print("log:", res["log"])
    print("TODO OK")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
