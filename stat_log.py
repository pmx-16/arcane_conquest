import csv
import os

CSV_FILE = "gamedata.csv"
FIELDNAMES = [
    "SessionID", "DistanceTraveled", "SurvivalTime", "EnemiesDefeated", "Score",
    "MagicBoltDamage", "ElectricBurstDamage", "ExplosionDamage",
    "ItemCollectionCount", "WaveNumber", "BossesDefeated", "PlayerLevel"
]

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

def log_stats(session_id, distance, survival_time, enemies_defeated, score,
              magicbolt_damage, electricburst_damage, explosion_damage,
              item_collection_count, wave_number, bosses_defeated, player_level):
    init_csv()
    row = {
        "SessionID": session_id,
        "DistanceTraveled": distance,
        "SurvivalTime": survival_time,
        "EnemiesDefeated": enemies_defeated,
        "Score": score,
        "MagicBoltDamage": magicbolt_damage,
        "ElectricBurstDamage": electricburst_damage,
        "ExplosionDamage": explosion_damage,
        "ItemCollectionCount": item_collection_count,
        "WaveNumber": wave_number,
        "BossesDefeated": bosses_defeated,
        "PlayerLevel": player_level
    }
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)