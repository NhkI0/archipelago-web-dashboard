"""Diagnostic: dump structure of the loaded multidata so we can see why slot_info isn't parsing."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from server.multidata import load_multidata

md = load_multidata("/opt/archipelago/output/latest.archipelago")

print("== top-level keys ==")
print(list(md.raw.keys()))

print("\n== slot_info ==")
si = md.raw.get("slot_info")
print("type:", type(si).__name__)
print("repr:", repr(si)[:800])

print("\n== slots (parsed) ==")
print("count:", len(md.slots))
for s in list(md.slots.values())[:5]:
    print(" ", s)

print("\n== games ==")
print(md.raw.get("games"))

print("\n== connect_names ==")
print(repr(md.raw.get("connect_names"))[:400])
