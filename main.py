import pygame
import tcod
import tcod.libtcodpy as libtcodpy
import random
import math
import uuid
from stat_log import log_stats, init_csv

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 16
MAP_WIDTH = 160
MAP_HEIGHT = 120
GAME_DURATION = 180  # 3 minutes session
BOSS_SPAWN_TIME = 70
FPS = 60
ZOOM_FACTOR = 1.5  # Camera zoom level
ITEM_SCALE_FACTOR = 1.5

class Camera:
    def __init__(self, width, height, tcod_map):
        self.width = width
        self.height = height
        self.tcod_map = tcod_map
        self.fov_map = tcod.map.Map(width=MAP_WIDTH, height=MAP_HEIGHT)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                self.fov_map.transparent[y, x] = tcod_map.transparent[y, x]
                self.fov_map.walkable[y, x] = tcod_map.walkable[y, x]
        self.x = 0
        self.y = 0
        self.zoom = ZOOM_FACTOR

    def update(self, player_x, player_y):
        self.x = player_x * TILE_SIZE * self.zoom - (self.width // 2)
        self.y = player_y * TILE_SIZE * self.zoom - (self.height // 2)
        self.fov_map.compute_fov(
            int(player_x), int(player_y),
            radius=20,
            light_walls=True,
            algorithm=libtcodpy.FOV_DIAMOND
        )

    def to_screen(self, x, y):
        screen_x = x * TILE_SIZE * self.zoom - self.x
        screen_y = y * TILE_SIZE * self.zoom - self.y
        return int(screen_x), int(screen_y)

class GameManager:
    def __init__(self):
        self.tcod_map = tcod.map.Map(width=MAP_WIDTH, height=MAP_HEIGHT)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                self.tcod_map.walkable[y, x] = True
                self.tcod_map.transparent[y, x] = True
        self.player = Player("Mage", [MAP_WIDTH // 2, MAP_HEIGHT // 2], self)
        self.enemies = []
        self.bosses = []
        self.items = []
        self.projectiles = []
        self.enemy_projectiles = []
        self.explosions = []
        self.current_wave = 0
        self.time_elapsed = 0
        self.score = 0
        self.enemies_killed = 0
        self.bosses_defeated = 0
        self.game_over = False
        self.game_won = False
        self.paused = False
        self.level_up_pending = False
        self.level_up_choices = []
        self.damage_dealt = 0
        self.cooldown_reduction = 0
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT, self.tcod_map)
        self.session_id = str(uuid.uuid4())
        self.enemies_defeated_per_wave = []
        self.current_wave_enemies_killed = 0

    def start_game(self):
        self.current_wave = 0
        self.spawn_enemies(10)

    def defeat_enemy(self, enemy):
        if enemy in self.enemies:
            self.enemies_killed += 1

    def update(self, dt):
        if self.game_over or self.game_won or self.paused or self.level_up_pending:
            return
        self.time_elapsed += dt
        if self.player.health <= 0:
            self.end_game()
        self.camera.update(self.player.position[0], self.player.position[1])
        self.player.update(dt, self.projectiles, self.enemies, self.explosions, self.time_elapsed)
        for item in self.items[:]:
            distance = ((self.player.position[0] - item.position[0])**2 + 
                       (self.player.position[1] - item.position[1])**2)**0.5
            if distance < 1:
                self.score += item.value
                if isinstance(item, Item):
                    item.apply_effect(self.player)
                elif isinstance(item, ExpOrb):
                    if self.player.gain_exp(item.exp):
                        self.trigger_level_up()
                self.items.remove(item)
            elif distance <= self.player.item_pickup_range:
                item.update(dt, self.player, self.tcod_map)
        if not self.enemies and not self.bosses and not self.game_over:
            self.enemies_defeated_per_wave.append(self.current_wave_enemies_killed)
            self.current_wave_enemies_killed = 0
            self.current_wave += 1
            self.spawn_enemies(self.current_wave + 10)
        if self.time_elapsed >= BOSS_SPAWN_TIME and not self.bosses:
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, 40)  # Spawn within 40 tiles
            x = self.player.position[0] + math.cos(angle) * distance
            y = self.player.position[1] + math.sin(angle) * distance
            x = max(0, min(MAP_WIDTH - 1, x))
            y = max(0, min(MAP_HEIGHT - 1, y))
            while abs(x - self.player.position[0]) < 1 and abs(y - self.player.position[1]) < 1:
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(5, 40)
                x = self.player.position[0] + math.cos(angle) * distance
                y = self.player.position[1] + math.sin(angle) * distance
                x = max(0, min(MAP_WIDTH - 1, x))
                y = max(0, min(MAP_HEIGHT - 1, y))
            self.bosses.append(Boss([x, y]))
        self.player.attack(self.projectiles, self.enemies, self.time_elapsed)
        for enemy in self.enemies[:]:
            enemy.update(dt, self.player, self.tcod_map, self.enemy_projectiles, self.time_elapsed, self)
            if enemy.is_dead and not enemy.is_animating:
                self.enemies.remove(enemy)
                self.score += 100
                self.current_wave_enemies_killed += 1
                orb = ExpOrb(list(enemy.position))
                self.items.append(orb)
                if random.random() < 0.15:
                    item_type = random.choice([Heal, Book])
                    self.items.append(item_type(list(enemy.position)))
        for projectile in self.projectiles[:]:
            projectile.update(dt, self.enemies, self)
        for enemy_projectile in self.enemy_projectiles[:]:
            enemy_projectile.update(dt, self.player, self)
            if not enemy_projectile.active:
                self.enemy_projectiles.remove(enemy_projectile)
        for explosion in self.explosions[:]:
            explosion.update(dt, self.enemies, self)
            if not explosion.active:
                self.explosions.remove(explosion)
        for boss in self.bosses[:]:
            boss.update(dt, self.player, self.tcod_map, self.enemy_projectiles, self.time_elapsed, self)
            if boss.health <= 0:
                self.defeat_boss(boss)
        if self.time_elapsed >= GAME_DURATION:
            self.win_game()

    def defeat_boss(self, boss):
        if boss in self.bosses:
            self.bosses.remove(boss)
            self.score += 1000
            self.bosses_defeated += 1
            orb = ExpOrb(list(boss.position), value=200, exp=50)
            self.items.append(orb)
            if random.random() < 0.8:
                item_type = random.choice([Heal, Book])
                self.items.append(item_type(list(boss.position)))

    def record_damage(self, amount):
        self.damage_dealt += amount

    def handle_events(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN and not self.game_over and not self.game_won:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif self.level_up_pending and event.key in [pygame.K_1, pygame.K_2, pygame.K_3]:
                    choice_idx = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2}.get(event.key)
                    if choice_idx < len(self.level_up_choices):
                        selected_upgrade = self.level_up_choices[choice_idx]
                        self.player.apply_upgrade(selected_upgrade)
                        self.level_up_pending = False
                        self.level_up_choices = []
            elif event.type == pygame.MOUSEBUTTONDOWN and (self.game_over or self.game_won):
                mouse_x, mouse_y = pygame.mouse.get_pos()
                retry_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 350, 200, 50)
                if retry_button_rect.collidepoint(mouse_x, mouse_y):
                    self.__init__()
                    self.start_game()
        if not self.paused and not self.level_up_pending and not self.game_over and not self.game_won:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_a]:
                self.player.move("left", self.tcod_map, dt)
            if keys[pygame.K_d]:
                self.player.move("right", self.tcod_map, dt)
            if keys[pygame.K_w]:
                self.player.move("up", self.tcod_map, dt)
            if keys[pygame.K_s]:
                self.player.move("down", self.tcod_map, dt)
        return True

    def spawn_enemies(self, count):
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, 30)
            x = self.player.position[0] + math.cos(angle) * distance
            y = self.player.position[1] + math.sin(angle) * distance
            x = max(0, min(MAP_WIDTH - 1, x))
            y = max(0, min(MAP_HEIGHT - 1, y))
            while abs(x - self.player.position[0]) < 1 and abs(y - self.player.position[1]) < 1:
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(5, 30)
                x = self.player.position[0] + math.cos(angle) * distance
                y = self.player.position[1] + math.sin(angle) * distance
                x = max(0, min(MAP_WIDTH - 1, x))
                y = max(0, min(MAP_HEIGHT - 1, y))
            enemy = Enemy([x, y])
            self.enemies.append(enemy)

    def trigger_level_up(self):
        self.level_up_pending = True
        self.level_up_choices = random.sample(
            ["hp_up", "atk_up", "cooldown_down", "magicbolt_count_up", "electricburst_count_up", "explosion_size_up"], 3)

    def end_game(self):
        self.game_over = True
        log_stats(
            session_id=self.session_id,
            distance=self.player.position[0],
            survival_time=self.time_elapsed,
            enemies_defeated=self.enemies_killed,
            score=self.score,
            magicbolt_damage=self.player.magic_damage["magicbolt"],
            electricburst_damage=self.player.magic_damage["electricburst"],
            explosion_damage=self.player.magic_damage["explosion"],
            item_collection_count=self.player.item_collection_count,
            wave_number=self.current_wave,
            bosses_defeated=self.bosses_defeated,
            player_level=self.player.level
        )

    def win_game(self):
        self.game_won = True
        log_stats(
            session_id=self.session_id,
            distance=self.player.position[0],
            survival_time=self.time_elapsed,
            enemies_defeated=self.enemies_killed,
            score=self.score,
            magicbolt_damage=self.player.magic_damage["magicbolt"],
            electricburst_damage=self.player.magic_damage["electricburst"],
            explosion_damage=self.player.magic_damage["explosion"],
            item_collection_count=self.player.item_collection_count,
            wave_number=self.current_wave,
            bosses_defeated=self.bosses_defeated,
            player_level=self.player.level
        )

class Player:
    def __init__(self, class_type, position, game_manager):
        self.class_type = class_type
        self.position = position
        self.health = 100
        self.max_health = 100
        self.mana = 100
        self.speed = 10
        self.game_manager = game_manager
        self.last_shot_time = 0
        self.last_explosion_time = 0
        self.last_electric_burst_time = 0
        self.frames = [pygame.image.load(f"Player/player ({i}).gif") for i in range(1, 14)]
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.1
        self.level = 1
        self.exp = 0
        self.exp_to_next_level = 100
        self.atk = 20
        self.magic_dmg_amp = 1.0
        self.magic_cooldown = 1.0
        self.explosion_cooldown = 7.0 * self.magic_cooldown
        self.electric_burst_cooldown = 4.0 * self.magic_cooldown
        self.item_pickup_range = 10
        self.magicbolt_count = 1
        self.electricburst_count = 1
        self.explosion_size_multiplier = 1.0
        self.pending_magicbolts = []
        self.pending_electricbursts = []
        self.item_collection_count = 0  # Track items collected
        self.magic_damage = {
            "magicbolt": 0,
            "electricburst": 0,
            "explosion": 0
        }  # Track damage per magic

        self.upgrade_info = {
            "hp_up": ("Health", "Increase HP by 10%", "Icons/hp_up.png"),
            "atk_up": ("Attack", "Increase attack by 10%", "Icons/atk_up.png"),
            "cooldown_down": ("Cooldown Reduction", "Reduce magic cooldown by 10%", "Icons/Cooldown.png"),
            "magicbolt_count_up": ("Magic Bolt Count", "Increase 1 Magic Bolt Count", "Icons/MagicBoltIcon.jpg"),
            "electricburst_count_up": ("Electric Burst Count", "Increase 1 Electric Burst Count", "Icons/ElectricBurstIcon.png"),
            "explosion_size_up": ("Explosion Size Increase", "Increase explosion size by 20%", "Icons/ExplosionIcon.png")
        }
        self.upgrade_icons = {}
        for upgrade, (_, _, icon_path) in self.upgrade_info.items():
            try:
                icon = pygame.image.load(icon_path)
                self.upgrade_icons[upgrade] = pygame.transform.scale(icon, (40, 40))
            except pygame.error:
                icon = pygame.Surface((40, 40))
                icon.fill((255, 0, 0))
                self.upgrade_icons[upgrade] = icon

    def gain_exp(self, amount):
        self.exp += amount
        leveled_up = False
        while self.exp >= self.exp_to_next_level:
            self.level_up()
            leveled_up = True
        return leveled_up

    def level_up(self):
        self.level += 1
        self.exp -= self.exp_to_next_level
        self.exp_to_next_level = 100 + (self.level - 1) * 10

    def apply_upgrade(self, upgrade):
        if upgrade == "hp_up":
            self.max_health *= 1.1
            self.health = min(self.health * 1.1, self.max_health)
        elif upgrade == "atk_up":
            self.atk *= 1.1
        elif upgrade == "cooldown_down":
            self.magic_cooldown = max(0.6, self.magic_cooldown * 0.9)
            self.explosion_cooldown = 7.0 * self.magic_cooldown
            self.electric_burst_cooldown = 4.0 * self.magic_cooldown
            self.game_manager.cooldown_reduction += 5
        elif upgrade == "magicbolt_count_up":
            self.magicbolt_count += 1
        elif upgrade == "electricburst_count_up":
            self.electricburst_count += 1
        elif upgrade == "explosion_size_up":
            self.explosion_size_multiplier *= 1.2

    def move(self, direction, tcod_map, dt):
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}.get(direction, (0, 0))
        new_x = self.position[0] + dx * self.speed * dt
        new_y = self.position[1] + dy * self.speed * dt
        if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and tcod_map.walkable[int(new_y), int(new_x)]):
            self.position[0] = new_x
            self.position[1] = new_y

    def update(self, dt, projectiles, enemies, explosions, time_elapsed):
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

        for i, (fire_time, position, direction, damage) in enumerate(self.pending_magicbolts[:]):
            if time_elapsed >= fire_time:
                projectile = Projectile(position, direction, damage)
                projectiles.append(projectile)
                self.pending_magicbolts.pop(i)

        for i, (fire_time, position, direction, damage) in enumerate(self.pending_electricbursts[:]):
            if time_elapsed >= fire_time:
                projectile = ElectricBurst(position, direction, damage)
                projectiles.append(projectile)
                self.pending_electricbursts.pop(i)

        if time_elapsed - self.last_explosion_time >= self.explosion_cooldown:
            self.fire_explosion(time_elapsed, explosions)

        if time_elapsed - self.last_electric_burst_time >= self.electric_burst_cooldown:
            self.fire_electric_burst(projectiles, enemies, explosions, time_elapsed)

    def attack(self, projectiles, enemies, time_elapsed):
        if not enemies and not self.game_manager.bosses:
            return
        if time_elapsed - self.last_shot_time >= 1:
            self.last_shot_time = time_elapsed
            closest_target = None
            min_distance = float('inf')
            for enemy in enemies:
                distance = (enemy.position[0] - self.position[0])**2 + (enemy.position[1] - self.position[1])**2
                if distance < min_distance:
                    min_distance = distance
                    closest_target = enemy
            for boss in self.game_manager.bosses:
                distance = (boss.position[0] - self.position[0])**2 + (boss.position[1] - self.position[1])**2
                if distance < min_distance:
                    min_distance = distance
                    closest_target = boss
            if closest_target:
                direction_x = closest_target.position[0] - self.position[0]
                direction_y = closest_target.position[1] - self.position[1]
                magnitude = (direction_x**2 + direction_y**2) ** 0.5
                if magnitude != 0:
                    direction_x /= magnitude
                    direction_y /= magnitude
                    for i in range(self.magicbolt_count):
                        delay = i * 0.35
                        fire_time = time_elapsed + delay
                        angle_offset = math.radians(random.uniform(-15, 15))
                        rotated_x = direction_x * math.cos(angle_offset) - direction_y * math.sin(angle_offset)
                        rotated_y = direction_x * math.sin(angle_offset) + direction_y * math.cos(angle_offset)
                        damage = self.atk * self.magic_dmg_amp
                        self.pending_magicbolts.append((
                            fire_time,
                            list(self.position),
                            (rotated_x, rotated_y),
                            damage
                        ))
                        self.magic_damage["magicbolt"] += damage

    def fire_explosion(self, time_elapsed, explosions_list):
        if time_elapsed - self.last_explosion_time >= self.explosion_cooldown:
            self.last_explosion_time = time_elapsed
            damage = self.atk * 2.4 * self.magic_dmg_amp
            explosion = FireExplosion(
                list(self.position),
                radius=12 * self.explosion_size_multiplier * (1 + 0.1 * (self.magic_dmg_amp - 1)),
                damage=damage
            )
            explosions_list.append(explosion)
            self.magic_damage["explosion"] += damage  # Track damage

    def fire_electric_burst(self, projectiles, enemies, explosions, time_elapsed):
        if not enemies and not self.game_manager.bosses:
            return
        if time_elapsed - self.last_electric_burst_time >= self.electric_burst_cooldown:
            self.last_electric_burst_time = time_elapsed
            closest_target = None
            min_distance = float('inf')
            for enemy in enemies:
                distance = (enemy.position[0] - self.position[0])**2 + (enemy.position[1] - self.position[1])**2
                if distance < min_distance:
                    min_distance = distance
                    closest_target = enemy
            for boss in self.game_manager.bosses:
                distance = (boss.position[0] - self.position[0])**2 + (boss.position[1] - self.position[1])**2
                if distance < min_distance:
                    min_distance = distance
                    closest_target = boss
            if closest_target:
                direction_x = closest_target.position[0] - self.position[0]
                direction_y = closest_target.position[1] - self.position[1]
                magnitude = (direction_x**2 + direction_y**2) ** 0.5
                if magnitude != 0:
                    direction_x /= magnitude
                    direction_y /= magnitude
                    for i in range(self.electricburst_count):
                        delay = i * 0.35
                        fire_time = time_elapsed + delay
                        angle_offset = math.radians(random.uniform(-15, 15))
                        rotated_x = direction_x * math.cos(angle_offset) - direction_y * math.sin(angle_offset)
                        rotated_y = direction_x * math.sin(angle_offset) + direction_y * math.cos(angle_offset)
                        damage = self.atk * 2.0 * self.magic_dmg_amp
                        self.pending_electricbursts.append((
                            fire_time,
                            list(self.position),
                            (rotated_x, rotated_y),
                            damage
                        ))
                        self.magic_damage["electricburst"] += damage  # Track damage

class AbstractEnemy:
    def __init__(self, position):
        self.position = position
        self.health = 250
        self.speed = 1.8
        self.scale_factor = 4
        self.state = 'idle'
        self.is_dead = False
        self.is_animating = False
        self.facing_right = True
        self.last_attack_time = 0
        self.attack_interval = 2
        self.attack_range = 20.0
        self.pending_projectile = False
        self.frames = []
        self.running_frames = []
        self.attacked_frames = []
        self.attack_frames = []
        self.death_frames = []
        self.idle_frames = []
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.1
        self.animation_timer = 0
        self.attacked_animation_duration = 0.6
        self.death_animation_duration = 1.7
        self.attack_animation_duration = 0.8
        self.was_moving = False

    def load_frames(self, frame_paths):
        try:
            for key, paths in frame_paths.items():
                frames = [pygame.image.load(path) for path in paths]
                if not frames:
                    raise ValueError(f"Failed to load {key} frames")
                setattr(self, f"{key}_frames", frames)
            self.frames = self.idle_frames
        except (pygame.error, FileNotFoundError, ValueError):
            for key in frame_paths:
                frame_count = len(frame_paths[key])
                frames = [pygame.Surface((32, 32)) for _ in range(frame_count)]
                for surface in frames:
                    surface.fill((255, 0, 0))
                setattr(self, f"{key}_frames", frames)
            self.frames = self.idle_frames

    def move(self, player, tcod_map, dt, game_manager):
        distance_to_player = ((self.position[0] - player.position[0])**2 + (self.position[1] - player.position[1])**2)**0.5
        if distance_to_player <= 9:
            dx, dy = 0, 0
        else:
            cost = tcod_map.walkable.astype('float32')
            cost[~tcod_map.walkable] = float('inf')
            astar = tcod.path.AStar(cost)
            start = (int(self.position[0]), int(self.position[1]))
            end = (int(player.position[0]), int(player.position[1]))
            path = astar.get_path(start[0], start[1], end[0], end[1])
            dx, dy = 0, 0
            if path and len(path) > 1:
                next_step = path[1]
                dx = next_step[0] - self.position[0]
                dy = next_step[1] - self.position[1]
                if dx < 0:
                    self.facing_right = False
                elif dx > 0:
                    self.facing_right = True
        new_x = self.position[0] + dx * self.speed * dt
        new_y = self.position[1] + dy * self.speed * dt
        if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and tcod_map.walkable[int(new_y), int(new_x)]):
            self.position[0] = new_x
            self.position[1] = new_y

    def take_damage(self, amount):
        if self.is_dead:
            return
        self.health -= amount
        game_manager = globals().get('game_manager')
        if game_manager:
            game_manager.record_damage(amount)
        if self.state != 'dead':
            self.start_attacked_animation()
        if self.health <= 0 and not self.is_dead:
            self.is_dead = True
            self.start_death_animation()

    def start_attacked_animation(self):
        if self.state != 'dead' and self.attacked_frames:
            self.state = 'attacked'
            self.frames = self.attacked_frames
            self.current_frame = 0
            self.frame_timer = 0
            self.animation_timer = 0
            self.is_animating = True

    def start_attack_animation(self):
        if self.state != 'dead':
            self.state = 'attacking'
            self.frames = self.attack_frames
            self.current_frame = 0
            self.frame_timer = 0
            self.animation_timer = 0
            self.is_animating = True
            self.pending_projectile = True

    def start_death_animation(self):
        self.state = 'dead'
        self.frames = self.death_frames
        self.current_frame = 0
        self.frame_timer = 0
        self.animation_timer = 0
        self.is_animating = True

    def attack(self, player, enemy_projectiles, time_elapsed):
        if self.is_dead or self.state == 'attacked':
            return
        distance = ((self.position[0] - player.position[0])**2 + (self.position[1] - player.position[1])**2)**0.5
        if distance <= self.attack_range and time_elapsed - self.last_attack_time >= self.attack_interval:
            self.start_attack_animation()
            self.last_attack_time = time_elapsed

    def fire_projectile(self, player, enemy_projectiles):
        direction_x = player.position[0] - self.position[0]
        direction_y = player.position[1] - self.position[1]
        magnitude = (direction_x**2 + direction_y**2)**0.5
        if magnitude != 0:
            direction_x /= magnitude
            direction_y /= magnitude
            projectile = EnemyProjectile(list(self.position), (direction_x, direction_y), damage=5)
            enemy_projectiles.append(projectile)

    def update(self, dt, player, tcod_map, enemy_projectiles, time_elapsed, game_manager):
        if self.is_dead and not self.is_animating:
            return
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration and self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0
        if self.is_animating:
            self.animation_timer += dt
            if self.state == 'attacked' and self.animation_timer >= self.attacked_animation_duration:
                self.state = 'idle'
                self.frames = self.idle_frames
                self.current_frame = 0
                self.is_animating = False
            elif self.state == 'attacking' and self.animation_timer >= self.attack_animation_duration:
                if self.pending_projectile:
                    self.fire_projectile(player, enemy_projectiles)
                    self.pending_projectile = False
                self.state = 'idle'
                self.frames = self.idle_frames
                self.current_frame = 0
                self.is_animating = False
            elif self.state == 'dead' and self.animation_timer >= self.death_animation_duration:
                self.is_animating = False
        if self.state not in ['dead', 'attacked', 'attacking']:
            old_position = self.position.copy()
            self.move(player, tcod_map, dt, game_manager)
            is_moving = (abs(old_position[0] - self.position[0]) > 0.01 or abs(old_position[1] - self.position[1]) > 0.01)
            if is_moving:
                self.state = 'running'
                self.frames = self.running_frames
            else:
                self.state = 'idle'
                self.frames = self.idle_frames
                self.current_frame = 0
            self.attack(player, enemy_projectiles, time_elapsed)

    def draw(self, screen, camera):
        if self.is_dead and not self.is_animating:
            return
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        if self.frames and self.current_frame < len(self.frames):
            frame = self.frames[self.current_frame]
            scaled_size = int(TILE_SIZE * self.scale_factor * camera.zoom)
            frame = pygame.transform.scale(frame, (scaled_size, scaled_size))
            if not self.facing_right:
                frame = pygame.transform.flip(frame, True, False)
            screen.blit(frame, (screen_x - scaled_size // 2, screen_y - scaled_size // 2))

class Enemy(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)
        self.scale_factor = 12
        frame_paths = {
            'running': [f"Enemies/Enemy ({i}).gif" for i in range(1, 6)],
            'attacked': [f"Enemies/Attacked/Attacked ({i}).gif" for i in range(1, 5)],
            'attack': [f"Enemies/Attack/Attack ({i}).gif" for i in range(1, 12)],
            'death': [f"Enemies/Death/death ({i}).gif" for i in range(1, 23)],
            'idle': [f"Enemies/Idle/Idle ({i}).gif" for i in range(1, 9)]
        }
        self.load_frames(frame_paths)

class EnemyProjectile:
    def __init__(self, position, direction, damage):
        self.position = position
        self.direction = direction
        self.damage = damage
        self.speed = 40
        self.state = 'moving'
        self.active = True
        self.scale_factor = 3.0
        try:
            self.moving_frames = [pygame.image.load(f"EnemiesProjectile/FlyingSlash/Slash ({i}).gif") for i in range(1, 6)]
            self.vanishing_frames = [pygame.image.load(f"EnemiesProjectile/SlashVanish/vanish ({i}).gif") for i in range(1, 4)]
            if not all([self.moving_frames, self.vanishing_frames]):
                raise ValueError("Some enemy projectile frames failed to load")
        except (pygame.error, FileNotFoundError, ValueError):
            self.moving_frames = [pygame.Surface((16, 16)) for _ in range(5)]
            self.vanishing_frames = [pygame.Surface((16, 16)) for _ in range(3)]
            for surface in self.moving_frames + self.vanishing_frames:
                surface.fill((255, 0, 255))
        self.frames = self.moving_frames
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.1
        self.vanish_timer = 0
        self.vanish_duration = 0.3
        self.angle = math.degrees(math.atan2(self.direction[1], self.direction[0]))
        self.rotated_frames = [pygame.transform.rotate(frame, -self.angle) for frame in self.moving_frames]
        self.vanishing_rotated_frames = [pygame.transform.rotate(frame, -self.angle) for frame in self.vanishing_frames]

    def update(self, dt, player, game_manager=None):
        if not self.active:
            return
        if self.state == 'moving':
            self.position[0] += self.direction[0] * self.speed * dt
            self.position[1] += self.direction[1] * self.speed * dt
            if abs(self.position[0] - player.position[0]) < 1 and abs(self.position[1] - player.position[1]) < 1:
                player.health -= self.damage
                self.state = 'vanishing'
                self.frames = self.vanishing_frames
                self.rotated_frames = self.vanishing_rotated_frames
                self.current_frame = 0
                self.frame_timer = 0
            if (self.position[0] < 0 or self.position[0] >= MAP_WIDTH or
                self.position[1] < 0 or self.position[1] >= MAP_HEIGHT):
                self.active = False
        elif self.state == 'vanishing':
            self.vanish_timer += dt
            if self.vanish_timer >= self.vanish_duration:
                self.active = False
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

    def draw(self, screen, camera):
        if not self.active:
            return
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        frame = self.rotated_frames[self.current_frame]
        original_size = frame.get_size()
        scaled_size = (int(original_size[0] * self.scale_factor * camera.zoom), int(original_size[1] * self.scale_factor * camera.zoom))
        frame = pygame.transform.scale(frame, scaled_size)
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class Boss(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)
        self.health = 300 * 2.5
        self.speed = 1.5 * 1.4
        self.scale_factor = 12
        self.attack_interval = 2 * 0.5
        self.attack_range = 20.0
        frame_paths = {
            'running': [f"Boss/Run/Run ({i}).gif" for i in range(1, 8)],
            'attack': [f"Boss/Attack/Attack ({i}).gif" for i in range(1, 7)],
            'death': [f"Boss/Death/Death ({i}).gif" for i in range(1, 8)],
            'idle': [f"Boss/Idle/Idle ({i}).gif" for i in range(1, 4)]
        }
        self.load_frames(frame_paths)
        self.attacked_frames = self.idle_frames  # Boss has no attacked frames

    def move(self, player, tcod_map, dt, game_manager):
        distance_to_player = ((self.position[0] - player.position[0])**2 + (self.position[1] - player.position[1])**2)**0.5
        if distance_to_player <= 9:
            dx, dy = 0, 0
        else:
            dx = player.position[0] - self.position[0]
            dy = player.position[1] - self.position[1]
            magnitude = (dx**2 + dy**2)**0.5
            if magnitude != 0:
                dx /= magnitude
                dy /= magnitude
                if dx < 0:
                    self.facing_right = False
                elif dx > 0:
                    self.facing_right = True
        new_x = self.position[0] + dx * self.speed * dt
        new_y = self.position[1] + dy * self.speed * dt
        if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and tcod_map.walkable[int(new_y), int(new_x)]):
            self.position[0] = new_x
            self.position[1] = new_y

    def fire_projectile(self, player, enemy_projectiles):
        direction_x = player.position[0] - self.position[0]
        direction_y = player.position[1] - self.position[1]
        magnitude = (direction_x**2 + direction_y**2)**0.5
        if magnitude != 0:
            direction_x /= magnitude
            direction_y /= magnitude
            for angle_offset in [-5, 5]:
                offset_rad = math.radians(angle_offset)
                rotated_x = direction_x * math.cos(offset_rad) - direction_y * math.sin(offset_rad)
                rotated_y = direction_x * math.sin(offset_rad) + direction_y * math.cos(offset_rad)
                projectile = BossProjectile(list(self.position), (rotated_x, rotated_y), damage=5 * 2)
                enemy_projectiles.append(projectile)

class BossProjectile:
    def __init__(self, position, direction, damage):
        self.position = position
        self.direction = direction
        self.damage = damage
        self.speed = 40
        self.active = True
        self.scale_factor = 3.0
        try:
            self.frames = [pygame.image.load(f"BossProjectile/BossBolt/Bolt ({i}).gif") for i in range(1, 30)]
        except (pygame.error, FileNotFoundError):
            self.frames = [pygame.Surface((16, 16)) for _ in range(30)]
            for frame in self.frames:
                frame.fill((255, 0, 255))
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.1
        self.angle = math.degrees(math.atan2(self.direction[1], self.direction[0]))
        self.rotated_frames = [pygame.transform.rotate(frame, -self.angle) for frame in self.frames]

    def update(self, dt, player, game_manager=None):
        if not self.active:
            return
        self.position[0] += self.direction[0] * self.speed * dt
        self.position[1] += self.direction[1] * self.speed * dt
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0
        if abs(self.position[0] - player.position[0]) < 1 and abs(self.position[1] - player.position[1]) < 1:
            player.health -= self.damage
            self.active = False
        if (self.position[0] < 0 or self.position[0] >= MAP_WIDTH or
            self.position[1] < 0 or self.position[1] >= MAP_HEIGHT):
            self.active = False

    def draw(self, screen, camera):
        if not self.active:
            return
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        frame = self.rotated_frames[self.current_frame]
        original_size = frame.get_size()
        scaled_size = (int(original_size[0] * self.scale_factor * camera.zoom), int(original_size[1] * self.scale_factor * camera.zoom))
        frame = pygame.transform.scale(frame, scaled_size)
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class FireExplosion:
    def __init__(self, position, radius=12, damage=48):
        self.position = position
        self.radius = radius
        self.damage = damage
        self.frames = [pygame.image.load(f"Explosion/Explosion ({i}).gif") for i in range(1, 13)]
        self.current_frame = 0
        self.frame_timer = 0.05
        self.active = True

    def update(self, dt, enemies, game_manager=None):
        if not self.active:
            return
        self.frame_timer += dt * 10
        if self.frame_timer >= 1:
            self.current_frame += 1
            self.frame_timer = 0
            if self.current_frame >= len(self.frames):
                self.active = False
                return
        if self.current_frame == 0:
            for enemy in enemies[:]:
                distance = ((enemy.position[0] - self.position[0])**2 + (enemy.position[1] - self.position[1])**2)**0.5
                if distance <= self.radius:
                    enemy.take_damage(self.damage)
                    if game_manager:
                        game_manager.record_damage(self.damage)
                    if enemy.health <= 0 and game_manager:
                        game_manager.defeat_enemy(enemy)
            if game_manager:
                for boss in game_manager.bosses[:]:
                    distance = ((boss.position[0] - self.position[0])**2 + (boss.position[1] - self.position[1])**2)**0.5
                    if distance <= self.radius:
                        boss.take_damage(self.damage)
                        if game_manager:
                            game_manager.record_damage(self.damage)
                        if boss.health <= 0:
                            game_manager.defeat_boss(boss)

    def draw(self, screen, camera):
        if not self.active:
            return
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        scaled_size = int(self.radius * TILE_SIZE * 2 * camera.zoom)
        frame = pygame.transform.scale(self.frames[self.current_frame], (scaled_size, scaled_size))
        screen.blit(frame, (screen_x - scaled_size // 2, screen_y - scaled_size // 2))

class Projectile:
    def __init__(self, position, direction, damage):
        self.position = position
        self.direction = direction
        self.damage = damage
        self.speed = 60
        self.frames = [pygame.image.load(f"Magicbolt/magicbolt ({i}).gif") for i in range(1, 30)]
        self.angle = math.degrees(math.atan2(self.direction[1], self.direction[0]))
        self.rotated_frames = [pygame.transform.rotate(frame, -self.angle) for frame in self.frames]
        self.current_frame = 0
        self.frame_timer = 0.02
        self.active = True

    def update(self, dt, enemies, game_manager=None):
        self.position[0] += self.direction[0] * self.speed * dt
        self.position[1] += self.direction[1] * self.speed * dt
        for enemy in enemies[:]:
            if abs(enemy.position[0] - self.position[0]) < 1 and abs(enemy.position[1] - self.position[1]) < 1:
                enemy.take_damage(self.damage)
                if game_manager:
                    game_manager.record_damage(self.damage)
                if enemy.health <= 0 and game_manager:
                    game_manager.defeat_enemy(enemy)
        if game_manager:
            for boss in game_manager.bosses[:]:
                if abs(boss.position[0] - self.position[0]) < 1 and abs(boss.position[1] - self.position[1]) < 1:
                    boss.take_damage(self.damage)
                    if game_manager:
                        game_manager.record_damage(self.damage)
                    if boss.health <= 0:
                        game_manager.defeat_boss(boss)
        self.frame_timer += dt * 10
        if self.frame_timer >= 1:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

    def draw(self, screen, camera):
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        frame = self.rotated_frames[self.current_frame]
        scaled_size = (int(frame.get_width() * camera.zoom), int(frame.get_height() * camera.zoom))
        frame = pygame.transform.scale(frame, scaled_size)
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class ElectricBurst(Projectile):
    def __init__(self, position, direction, damage):
        super().__init__(position, direction, damage)
        self.speed = 7.5
        self.frames = [pygame.image.load(f"ElectricBurst/electricburst ({i}).png") for i in range(1, 16)]
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.143
        self.active = True
        self.aoe_range = 3
        self.aoe_damage = damage
        self.damage_timer = 0
        self.damage_interval = 0.5
        self.cycle_completed = False

    def update(self, dt, enemies, game_manager=None):
        if not self.active:
            return
        self.position[0] += self.direction[0] * self.speed * dt
        self.position[1] += self.direction[1] * self.speed * dt
        self.damage_timer += dt
        if self.damage_timer >= self.damage_interval:
            for enemy in enemies[:]:
                distance = ((enemy.position[0] - self.position[0])**2 + (enemy.position[1] - self.position[1])**2)**0.5
                if distance <= self.aoe_range:
                    enemy.take_damage(self.aoe_damage)
                    if game_manager:
                        game_manager.record_damage(self.aoe_damage)
                    if enemy.health <= 0 and game_manager:
                        game_manager.defeat_enemy(enemy)
            if game_manager:
                for boss in game_manager.bosses[:]:
                    distance = ((boss.position[0] - self.position[0])**2 + (boss.position[1] - self.position[1])**2)**0.5
                    if distance <= self.aoe_range:
                        boss.take_damage(self.aoe_damage)
                        if game_manager:
                            game_manager.record_damage(self.aoe_damage)
                        if boss.health <= 0:
                            game_manager.defeat_boss(boss)
            self.damage_timer = 0
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration:
            self.current_frame += 1
            if self.current_frame >= len(self.frames):
                self.current_frame = 0
                self.cycle_completed = True
            self.frame_timer = 0
        if self.cycle_completed:
            self.active = False
        if (self.position[0] < 0 or self.position[0] >= MAP_WIDTH or
            self.position[1] < 0 or self.position[1] >= MAP_HEIGHT):
            self.active = False

    def draw(self, screen, camera):
        if not self.active:
            return
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        frame = self.frames[self.current_frame]
        original_size = frame.get_size()
        scaled_size = (int(original_size[0] * 3 * camera.zoom), int(original_size[1] * 3 * camera.zoom))
        frame = pygame.transform.scale(frame, scaled_size)
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class Item:
    def __init__(self, position, value=50):
        self.position = position
        self.value = value
        self.radius = 4 * ITEM_SCALE_FACTOR  # Scale hitbox
        self.speed = 16
        self.image = None
        self.item_type = "generic"

    def update(self, dt, player, tcod_map):
        direction_x = player.position[0] - self.position[0]
        direction_y = player.position[1] - self.position[1]
        distance = (direction_x**2 + direction_y**2)**0.5
        if distance > 0:
            direction_x /= distance
            direction_y /= distance
            self.position[0] += direction_x * self.speed * dt
            self.position[1] += direction_y * self.speed * dt

    def draw(self, screen, camera):
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        if self.image:
            scaled_size = int(self.radius * 2 * camera.zoom * ITEM_SCALE_FACTOR)
            scaled_image = pygame.transform.scale(self.image, (scaled_size, scaled_size))
            screen.blit(scaled_image, (screen_x - scaled_size // 2, screen_y - scaled_size // 2))
        else:
            pygame.draw.circle(screen, (255, 255, 0), (screen_x, screen_y), int(self.radius * camera.zoom))

class Heal(Item):
    def __init__(self, position):
        super().__init__(position, value=100)
        self.item_type = "heal"
        try:
            self.image = pygame.image.load("Items/heal.png")
            self.image = pygame.transform.scale(self.image, 
                (int(16 * ITEM_SCALE_FACTOR), int(16 * ITEM_SCALE_FACTOR)))
        except pygame.error:
            self.image = pygame.Surface((int(16 * ITEM_SCALE_FACTOR), int(16 * ITEM_SCALE_FACTOR)))
            self.image.fill((0, 255, 0))

    def apply_effect(self, player):
        heal_amount = player.max_health * 0.15
        player.health = min(player.health + heal_amount, player.max_health)
        player.item_collection_count += 1

class Book(Item):
    def __init__(self, position):
        super().__init__(position, value=100)
        self.item_type = "book"
        try:
            self.image = pygame.image.load("Items/book.png")
            self.image = pygame.transform.scale(self.image, 
                (int(16 * ITEM_SCALE_FACTOR), int(16 * ITEM_SCALE_FACTOR)))
        except pygame.error:
            self.image = pygame.Surface((int(16 * ITEM_SCALE_FACTOR), int(16 * ITEM_SCALE_FACTOR)))
            self.image.fill((255, 0, 0))

    def apply_effect(self, player):
        player.atk *= 1.05  # Permanent 5% attack increase
        player.item_collection_count += 1

class ExpOrb:
    def __init__(self, position, value=50, exp=10):
        self.position = position
        self.value = value
        self.exp = exp
        self.radius = 4
        self.color = (0, 0, 255)
        self.speed = 16

    def update(self, dt, player, tcod_map):
        direction_x = player.position[0] - self.position[0]
        direction_y = player.position[1] - self.position[1]
        distance = (direction_x**2 + direction_y**2)**0.5
        if distance > 0:
            direction_x /= distance
            direction_y /= distance
            self.position[0] += direction_x * self.speed * dt
            self.position[1] += direction_y * self.speed * dt

    def draw(self, screen, camera):
        screen_x, screen_y = camera.to_screen(self.position[0], self.position[1])
        pygame.draw.circle(screen, self.color, (screen_x, screen_y), int(self.radius * camera.zoom))

def map_to_screen(x, y):
    return int(x * TILE_SIZE), int(y * TILE_SIZE)

def draw_map(screen, tcod_map, camera):
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            if camera.fov_map.fov[y, x]:
                tile_surface = pygame.Surface((int(TILE_SIZE * camera.zoom), int(TILE_SIZE * camera.zoom)), pygame.SRCALPHA)
                color = (100, 100, 100, 128) if tcod_map.walkable[y, x] else (0, 0, 0, 128)
                tile_surface.fill(color)
                screen_x, screen_y = camera.to_screen(x, y)
                screen.blit(tile_surface, (screen_x, screen_y))

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Arcane Conquest")
    try:
        background_image = pygame.image.load("Background/background1.png")
        background_image = pygame.transform.scale(background_image, 
            (int(SCREEN_WIDTH / ZOOM_FACTOR), int(SCREEN_HEIGHT / ZOOM_FACTOR)))
    except pygame.error as e:
        print(f"Error loading background image: {e}")
        background_image = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    init_csv()
    game_manager = GameManager()
    game_manager.start_game()
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        font = pygame.font.SysFont(None, 48)
        stats_font = pygame.font.SysFont(None, 36)
        small_font = pygame.font.SysFont(None, 24)
        running = game_manager.handle_events(dt)
        game_manager.update(dt)
        screen.fill((0, 0, 0))
        scaled_bg = pygame.transform.scale(background_image, 
            (int(background_image.get_width() * ZOOM_FACTOR), int(background_image.get_height() * ZOOM_FACTOR)))
        screen.blit(scaled_bg, (0, 0))
        draw_map(screen, game_manager.tcod_map, game_manager.camera)
        exp_bar_width = SCREEN_WIDTH
        exp_bar_height = 10
        exp_percentage = game_manager.player.exp / game_manager.player.exp_to_next_level
        filled_width = exp_bar_width * min(exp_percentage, 1.0)
        pygame.draw.rect(screen, (50, 50, 50), (0, 0, exp_bar_width, exp_bar_height))
        pygame.draw.rect(screen, (0, 0, 255), (0, 0, filled_width, exp_bar_height))
        level_text = font.render(f"Level: {game_manager.player.level}", True, (255, 255, 255))
        screen.blit(level_text, (10, exp_bar_height + 5))
        score_text = font.render(f"Score: {game_manager.score}", True, (255, 255, 255))
        wave_text = font.render(f"Wave: {game_manager.current_wave}", True, (255, 255, 255))
        screen.blit(score_text, (10, exp_bar_height + 45))
        screen.blit(wave_text, (10, exp_bar_height + 85))
        player_x, player_y = game_manager.camera.to_screen(*game_manager.player.position)
        frame = game_manager.player.frames[game_manager.player.current_frame]
        scaled_size = int(TILE_SIZE * 4 * game_manager.camera.zoom)
        frame = pygame.transform.scale(frame, (scaled_size, scaled_size))
        screen.blit(frame, (player_x - scaled_size // 2, player_y - scaled_size // 2))
        health_bar_width = int(TILE_SIZE * 4 * game_manager.camera.zoom)
        health_bar_height = int(5 * game_manager.camera.zoom)
        health_percentage = game_manager.player.health / game_manager.player.max_health
        filled_width = health_bar_width * health_percentage
        health_bar_x = player_x - (health_bar_width // 2)
        health_bar_y = player_y + (scaled_size // 2) + 2
        pygame.draw.rect(screen, (255, 0, 0), (health_bar_x, health_bar_y, health_bar_width, health_bar_height))
        pygame.draw.rect(screen, (0, 255, 0), (health_bar_x, health_bar_y, filled_width, health_bar_height))
        
        for enemy in game_manager.enemies:
            if game_manager.camera.fov_map.fov[int(enemy.position[1]), int(enemy.position[0])]:
                enemy.draw(screen, game_manager.camera)

        for item in game_manager.items:
            if game_manager.camera.fov_map.fov[int(item.position[1]), int(item.position[0])]:
                item.draw(screen, game_manager.camera)
                
        for boss in game_manager.bosses:
            if game_manager.camera.fov_map.fov[int(boss.position[1]), int(boss.position[0])]:
                boss.draw(screen, game_manager.camera)
                boss_health_bar_width = 400
                boss_health_bar_height = 20
                boss_health_percentage = boss.health / (300 * 2.5)
                boss_filled_width = boss_health_bar_width * max(0, boss_health_percentage)
                boss_health_bar_x = (SCREEN_WIDTH - boss_health_bar_width) // 2
                boss_health_bar_y = exp_bar_height + 45
                pygame.draw.rect(screen, (255, 0, 0), (boss_health_bar_x, boss_health_bar_y, boss_health_bar_width, boss_health_bar_height))
                pygame.draw.rect(screen, (0, 255, 0), (boss_health_bar_x, boss_health_bar_y, boss_filled_width, boss_health_bar_height))
                boss_health_text = small_font.render(f"Boss HP: {int(boss.health)}/{int(300 * 2.5)}", True, (255, 255, 255))
                screen.blit(boss_health_text, (boss_health_bar_x, boss_health_bar_y - 25))
                
        for projectile in game_manager.projectiles[:]:
            x, y = int(projectile.position[0]), int(projectile.position[1])
            if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and game_manager.camera.fov_map.fov[y, x]:
                projectile.draw(screen, game_manager.camera)

        for enemy_projectile in game_manager.enemy_projectiles[:]:
            x, y = int(enemy_projectile.position[0]), int(enemy_projectile.position[1])
            if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and game_manager.camera.fov_map.fov[y, x]:
                enemy_projectile.draw(screen, game_manager.camera)
                
        for explosion in game_manager.explosions[:]:
            x, y = int(explosion.position[0]), int(explosion.position[1])
            if 0 <= x < MAP_WIDTH and 0 <= y < MAP_HEIGHT and game_manager.camera.fov_map.fov[y, x]:
                explosion.draw(screen, game_manager.camera)
                
        if game_manager.paused:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
            pause_text = font.render("Paused - Character Stats", True, (255, 255, 255))
            screen.blit(pause_text, (SCREEN_WIDTH // 2 - pause_text.get_width() // 2, 50))
            stats_y = 150
            stats_spacing = 60
            center_x = SCREEN_WIDTH // 2
            core_stats = [
                (u"\u2665", f"HP: {game_manager.player.health:.1f}/{game_manager.player.max_health:.1f}"),
                (u"\u2694", f"ATK: {game_manager.player.atk:.1f}"),
                (u"\u2728", f"Magic Damage: {game_manager.player.magic_dmg_amp:.1f}x"),
                (u"\u23F2", f"Cooldown Reduction: {game_manager.cooldown_reduction}%")
            ]
            for i, (icon, stat) in enumerate(core_stats):
                icon_text = small_font.render(icon, True, (255, 255, 255))
                stat_text = stats_font.render(stat, True, (255, 255, 255))
                icon_x = center_x - stat_text.get_width() // 2 - 40
                screen.blit(icon_text, (icon_x, stats_y + i * stats_spacing))
                screen.blit(stat_text, (center_x - stat_text.get_width() // 2, stats_y + i * stats_spacing))
            game_stats_y = stats_y + len(core_stats) * stats_spacing + 80
            game_stats = [
                f"Current Level: {game_manager.player.level}",
                f"Time Survived: {int(game_manager.time_elapsed)}s",
                f"Enemies Killed: {game_manager.enemies_killed}"
            ]
            for i, stat in enumerate(game_stats):
                stat_text = stats_font.render(stat, True, (255, 255, 255))
                screen.blit(stat_text, (SCREEN_WIDTH // 2 - stat_text.get_width() // 2, game_stats_y + i * 40))
                
        if game_manager.level_up_pending:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
            title_text = font.render("Level Up! Choose an Upgrade (1, 2, 3)", True, (255, 255, 255))
            screen.blit(title_text, (SCREEN_WIDTH // 2 - title_text.get_width() // 2, 50))
            box_width = 400
            box_height = 100
            box_spacing = 10
            start_x = (SCREEN_WIDTH - box_width) // 2
            box_y = 150
            for i, choice in enumerate(game_manager.level_up_choices):
                upgrade_name, description, _ = game_manager.player.upgrade_info[choice]
                icon = game_manager.player.upgrade_icons[choice]
                level_text = str(i + 1)
                current_y = box_y + i * (box_height + box_spacing)
                pygame.draw.rect(screen, (100, 100, 100), (start_x, current_y, box_width, box_height))
                pygame.draw.rect(screen, (255, 255, 255), (start_x, current_y, box_width, box_height), 2)
                screen.blit(icon, (start_x + 10, current_y + 10))
                name_text = stats_font.render(upgrade_name, True, (255, 255, 255))
                screen.blit(name_text, (start_x + 60, current_y + 10))
                keybind_text = small_font.render(level_text, True, (255, 255, 0))
                screen.blit(keybind_text, (start_x + box_width - keybind_text.get_width() - 10, current_y + 10))
                desc_text = small_font.render(description, True, (255, 255, 255))
                screen.blit(desc_text, (start_x + 60, current_y + 40))

        if game_manager.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
            game_over_font = pygame.font.SysFont(None, 40)
            game_over_text = game_over_font.render("You died", True, (255, 0, 0))
            screen.blit(game_over_text, (SCREEN_WIDTH // 2 - game_over_text.get_width() // 2, 50))
            stats_y = 120
            stats_spacing = 50
            center_x = SCREEN_WIDTH // 2
            overall_stats = [
                f"Survival Time: {int(game_manager.time_elapsed)}s",
                f"Enemies Defeated: {game_manager.enemies_killed}",
                f"Waves Completed: {game_manager.current_wave}",
                f"Score: {game_manager.score}",
                f"Damage Dealt: {int(game_manager.damage_dealt)}"
            ]
            for i, stat in enumerate(overall_stats):
                stat_text = game_over_font.render(stat, True, (255, 255, 255))
                screen.blit(stat_text, (center_x - stat_text.get_width() // 2, stats_y + i * stats_spacing))
            retry_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 350, 200, 50)
            pygame.draw.rect(screen, (0, 255, 0), retry_button_rect)
            retry_text = game_over_font.render("Retry", True, (0, 0, 0))
            screen.blit(retry_text, (SCREEN_WIDTH // 2 - retry_text.get_width() // 2, 360))

        if game_manager.game_won:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))
            game_over_font = pygame.font.SysFont(None, 40)
            win_text = game_over_font.render("You Win", True, (255, 255, 0))
            screen.blit(win_text, (SCREEN_WIDTH // 2 - win_text.get_width() // 2, 50))
            stats_y = 120
            stats_spacing = 50
            center_x = SCREEN_WIDTH // 2
            overall_stats = [
                f"Survival Time: {int(game_manager.time_elapsed)}s",
                f"Enemies Defeated: {game_manager.enemies_killed}",
                f"Waves Completed: {game_manager.current_wave}",
                f"Score: {game_manager.score}",
                f"Damage Dealt: {int(game_manager.damage_dealt)}"
            ]
            for i, stat in enumerate(overall_stats):
                stat_text = game_over_font.render(stat, True, (255, 255, 255))
                screen.blit(stat_text, (center_x - stat_text.get_width() // 2, stats_y + i * stats_spacing))
            retry_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, 350, 200, 50)
            pygame.draw.rect(screen, (0, 255, 0), retry_button_rect)
            play_again_text = game_over_font.render("Play Again", True, (0, 0, 0))
            screen.blit(play_again_text, (SCREEN_WIDTH // 2 - play_again_text.get_width() // 2, 360))
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()