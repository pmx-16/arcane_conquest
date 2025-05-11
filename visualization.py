import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("gamedata.csv")
df["Session"] = range(1, len(df) + 1)

damage_stats = pd.DataFrame([
    {"perk": "Magic Bolt", "mean": df["MagicBoltDamage"].mean(), "std": df["MagicBoltDamage"].std()},
    {"perk": "Electric Burst", "mean": df["ElectricBurstDamage"].mean(), "std": df["ElectricBurstDamage"].std()},
    {"perk": "Explosion", "mean": df["ExplosionDamage"].mean(), "std": df["ExplosionDamage"].std()}
])

wave_data = df.groupby("WaveNumber")["EnemiesDefeated"].mean().reset_index()
wave_data["WaveNumber"] = wave_data["WaveNumber"].astype(int)
df["TotalDamage"] = df["MagicBoltDamage"] + df["ElectricBurstDamage"] + df["ExplosionDamage"]

plt.style.use("ggplot")
fig, axs = plt.subplots(3, 2, figsize=(18, 12))
fig.suptitle("Gameplay Statistics", fontsize=20, fontweight="bold")

# Graph 1: Distant Traveled vs Survival Time
axs[0, 0].scatter(df["SurvivalTime"], df["DistanceTraveled"], color="tab:blue", alpha=0.6)
axs[0, 0].set_title("Distant Traveled vs Survival Time")
axs[0, 0].set_xlabel("Survival Time (s)")
axs[0, 0].set_ylabel("Distance Traveled (tiles)")
axs[0, 0].set_xlim(0, df["SurvivalTime"].max() + 20)
axs[0, 0].set_ylim(0, df["DistanceTraveled"].max() + 10)

# Graph 2: Enemies Defeated Per Wave
sns.barplot(x="WaveNumber", y="EnemiesDefeated", data=wave_data, ax=axs[0, 1], color="tab:orange")
axs[0, 1].set_title("Enemies Defeated Per Wave")
axs[0, 1].set_xlabel("Wave Number")
axs[0, 1].set_ylabel("Average Enemies Defeated")
axs[0, 1].set_ylim(0, wave_data["EnemiesDefeated"].max() + 20)

# Graph 3: Enemies Defeated vs. Distance Traveled
axs[1, 0].scatter(df["DistanceTraveled"], df["EnemiesDefeated"], color="tab:brown", alpha=0.6)
axs[1, 0].set_title("Enemies Defeated vs. Distance Traveled")
axs[1, 0].set_xlabel("Distance Traveled (tiles)")
axs[1, 0].set_ylabel("Enemies Defeated")
axs[1, 0].set_xlim(0, df["DistanceTraveled"].max() + 10)
axs[1, 0].set_ylim(0, df["EnemiesDefeated"].max() + 20)

# Graph 4: Damage Output Per Magic
sns.barplot(x="perk", y="mean", data=damage_stats, ax=axs[1, 1], color="tab:red")
axs[1, 1].errorbar(x=damage_stats["perk"], y=damage_stats["mean"], yerr=damage_stats["std"], fmt="none", c="black", capsize=5)
axs[1, 1].set_title("Damage Output Per Magic")
axs[1, 1].set_xlabel("Perk")
axs[1, 1].set_ylabel("Mean Damage")
axs[1, 1].set_ylim(0, damage_stats["mean"].max() + damage_stats["std"].max())

# Graph 5: Survival Time Per Session
axs[2, 0].plot(df["Session"], df["SurvivalTime"], marker="o", color="tab:purple")
axs[2, 0].set_title("Survival Time Per Session")
axs[2, 0].set_xlabel("Session")
axs[2, 0].set_ylabel("Survival Time (s)")
axs[2, 0].set_ylim(0, df["SurvivalTime"].max() + 20)

# Graph 6: Total Damage Dealt vs. Survival Time
axs[2, 1].scatter(df["SurvivalTime"], df["TotalDamage"], color="tab:cyan", alpha=0.6)
axs[2, 1].set_title("Total Damage Dealt vs. Survival Time")
axs[2, 1].set_xlabel("Survival Time (s)")
axs[2, 1].set_ylabel("Total Damage")
axs[2, 1].set_xlim(0, df["SurvivalTime"].max() + 20)
axs[2, 1].set_ylim(0, df["TotalDamage"].max() + 1000)

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.subplots_adjust(hspace=0.5)

# Save plot
plt.savefig("visualization.png")