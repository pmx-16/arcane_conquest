# Installation Guide
## Cloning
clone this repository into local using this command
```powershell
git clone https://github.com/pmx-16/arcane_conquest.git
```
## Install neccesary library
```powershell
pip install -r requirements.txt
```

### Run main game

```bash
python main.py
```

### Run visualizations

```bash
python visualizations.py
```

## Features (V1.0)
### Core Gameplay
- Player use every magic automatically to the nearest enemy
- Player need to dodge bullet hell and survive exactly 3 minutes to win the game
- Player are given randomized perk option when they leveled up
- Planning Perks and Positioning are top priority for survival
### Difficulty System
- 10 Enemies spawn at the start of the game
- Waves progress as all enemies in the current waves are defeated
- Number of enemies goes up by 1 for each wave
### Enemy System
- Each enemies drop blue exp orb on death, with 15% chance to drop heal item and book
- Each enemies defeated will give 100 score
- Boss will start spawning every wave after 70 seconds into the game
- Boss will give 1000 score when defeated
- Boss drop more blue exp orb on death, and 80% chance to drop healing item and book
- Both enemies and boss will walk toward player until cirtain range and begin firing their projectile
### Magic
- Magic bolt are automatically fired to the closest enemy
- Fire explosion are automatically trigger and will explode with player as the center of the skill damaging every enemies in its range
- Electric burst function similar to projectile but with damage interval and slower speed hiting every enemy within its radius
### Perks & Items
- Cooldown Reduction: Reduce magic cooldown by 10%, capped at 40% maximum
- Attack: Increase attack by 10%
- Health: Increase HP by 10%
- Magic Bolt Count: Increase 1 Magic Bolt Count
- Electric Burst Count: Increase 1 Electric Burst Count
- Explosion Size Increase: Increase Explosion size by 20%
- Book(Item): Permanently increase player's attack by 5%
- Heal(Item): Restore player's health by 15%
### Keybinds
- W,A,S,D for moving up, left, down, right
- Esc for pausing the game
- 1,2,3 for choosing perk
### Data Logging
- Game Data are logged at every end of game session
- Logged data: 
- DistanceTraveled, SurvivalTime, EnemiesDefeated, Score,
- MagicBoltDamage, ElectricBurstDamage, ExplosionDamage,
- ItemCollectionCount, WaveNumber, BossesDefeated, PlayerLevel