#!/usr/bin/env python3
# Diagnostik MDPS untuk Stargazer Non-SCC.
# Menampilkan bit MDPS12 (ToiUnavail / ToiActive / ToiFlt) + status lateral openpilot
# secara real-time, supaya bisa dilihat bit mana yang nyala dan pada kecepatan berapa.
#
# Jalankan di device (mobil ON, openpilot berjalan):
#   cd /data/openpilot && python selfdrive/debug/mdps_diag.py
# Bisa juga dari PC yang terhubung ke device:
#   python selfdrive/debug/mdps_diag.py --addr <IP_DEVICE>

import argparse

import cereal.messaging as messaging
from common.realtime import sec_since_boot
from opendbc.can.parser import CANParser
from selfdrive.config import Conversions as CV

# MDPS12 ada di bus 0 (sama seperti carstate get_can_parser).
DBC = "hyundai_kia_generic"
BUS = 0

SIGNALS = [
  ("CF_Mdps_ToiUnavail", "MDPS12", 0),  # bit 12 — Torque Input Unavailable
  ("CF_Mdps_ToiActive",  "MDPS12", 0),  # bit 13 — Torque Input Active (MDPS sedang assist)
  ("CF_Mdps_ToiFlt",     "MDPS12", 0),  # bit 14 — Torque Input Fault
  ("CR_Mdps_StrColTq",   "MDPS12", 0),  # torsi kolom setir (driver)
  ("CR_Mdps_OutTq",      "MDPS12", 0),  # torsi output EPS
]
CHECKS = [("MDPS12", 50)]


def yn(v):
  return "\033[91mYA \033[0m" if v else "\033[92m-  \033[0m"  # merah=YA, hijau=-


def main(addr):
  cp = CANParser(DBC, SIGNALS, CHECKS, BUS)
  logcan = messaging.sub_sock("can", addr=addr)
  sm = messaging.SubMaster(["carState"], addr=addr)

  unavail_seen = active_seen = flt_seen = False
  start = sec_since_boot()
  last_print = 0.

  print("Membaca MDPS12 di bus 0 ... (Ctrl+C untuk berhenti)\n")

  while True:
    can_strings = messaging.drain_sock_raw(logcan, wait_for_one=True)
    cp.update_strings(can_strings)
    sm.update(0)

    toi_unavail = cp.vl["MDPS12"]["CF_Mdps_ToiUnavail"]
    toi_active  = cp.vl["MDPS12"]["CF_Mdps_ToiActive"]
    toi_flt     = cp.vl["MDPS12"]["CF_Mdps_ToiFlt"]
    col_tq      = cp.vl["MDPS12"]["CR_Mdps_StrColTq"]
    out_tq      = cp.vl["MDPS12"]["CR_Mdps_OutTq"]

    # latch: ingat kalau bit pernah nyala selama sesi
    unavail_seen = unavail_seen or bool(toi_unavail)
    active_seen  = active_seen  or bool(toi_active)
    flt_seen     = flt_seen     or bool(toi_flt)

    cs = sm["carState"]
    v_kph = cs.vEgo * CV.MS_TO_KPH
    steer_warning = cs.steerWarning
    avail = cs.cruiseState.available
    enabled = cs.cruiseState.enabled
    lfa = bool(getattr(cs, "lfaEnabled", False))

    if sec_since_boot() - last_print > 0.2:
      dd = chr(27) + "[2J" + chr(27) + "[H"  # clear + home
      dd += f"  t={sec_since_boot() - start:6.1f}s   kecepatan={v_kph:5.1f} km/h\n"
      dd += "  " + "-" * 46 + "\n"
      dd += f"  MDPS ToiUnavail : {yn(toi_unavail)}   (pernah nyala: {yn(unavail_seen)})\n"
      dd += f"  MDPS ToiActive  : {yn(toi_active)}   (pernah nyala: {yn(active_seen)})\n"
      dd += f"  MDPS ToiFlt     : {yn(toi_flt)}   (pernah nyala: {yn(flt_seen)})\n"
      dd += f"  Torsi kolom/out : {col_tq:7.1f} / {out_tq:7.1f}\n"
      dd += "  " + "-" * 46 + "\n"
      dd += "  openpilot:\n"
      dd += f"    steerWarning      : {yn(steer_warning)}\n"
      dd += f"    lfaEnabled (LFA)  : {yn(lfa)}\n"
      dd += f"    cruise available  : {yn(avail)}\n"
      dd += f"    cruise enabled    : {yn(enabled)}\n"
      dd += "  " + "-" * 46 + "\n"
      dd += "  Catatan: steerWarning = ToiUnavail ATAU ToiFlt.\n"
      dd += "  Cek apakah ToiUnavail nyala saat diam lalu hilang\n"
      dd += "  saat jalan cepat (=deadlock idle), atau nyala terus\n"
      dd += "  (=relay/bus), atau ToiFlt nyala (=fault aktif).\n"
      print(dd)
      last_print = sec_since_boot()


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Diagnostik MDPS Stargazer (bit ToiUnavail/ToiActive/ToiFlt)")
  parser.add_argument("--addr", default="127.0.0.1", help="IP device (default lokal di device)")
  args = parser.parse_args()
  try:
    main(args.addr)
  except KeyboardInterrupt:
    print("\nberhenti.")
