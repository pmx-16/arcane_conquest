import pygame
import tcod
import random
import math

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TILE_SIZE = 16
MAP_WIDTH = 80
MAP_HEIGHT = 60
FPS = 60

class GameManager:
    def __init__(self):
        self.tcod_map = tcod.map.Map(width=MAP_WIDTH, height=MAP_HEIGHT)
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                self.tcod_map.walkable[y, x] = True
                self.tcod_map.transparent[y, x] = True
        self.player = Player("Mage", [MAP_WIDTH // 2, MAP_HEIGHT // 2])
        self.enemies = []
        self.bosses = []
        self.items = []
        self.projectiles = []
        self.explosions = []
        self.current_wave = 0
        self.time_elapsed = 0
        self.score = 0
        self.game_over = False

    def start_game(self):
        self.current_wave = 0
        self.spawn_enemies(10)

    def defeat_enemy(self, enemy):
        if enemy in self.enemies:
            self.enemies.remove(enemy)
            self.score += 100
            orb = ExpOrb(list(enemy.position))
            self.items.append(orb)
            print(f"Enemy defeated at {enemy.position}! Score: {self.score}, dropped EXP orb")

    def defeat_boss(self, boss):
        if boss in self.bosses:
            self.bosses.remove(boss)
            self.score += 50
            print(f"Boss defeated! Score: {self.score}")

    def update(self, dt):
        if self.game_over:
            return
        self.time_elapsed += dt

        if self.player.health <= 0:
            self.end_game()

        self.player.update(dt)

        for item in self.items[:]:
            distance = ((self.player.position[0] - item.position[0])**2 + 
                       (self.player.position[1] - item.position[1])**2)**0.5
            if distance < 1:
                self.score += item.value
                self.items.remove(item)
                print(f"Collected EXP orb! Score: {self.score}")

        if not self.enemies and not self.game_over:
            self.current_wave += 1
            self.spawn_enemies(self.current_wave + 10)
            print(f"Wave {self.current_wave} started with {self.current_wave + 10} enemies")

        self.player.attack(self.projectiles, self.enemies, self.time_elapsed)

        for enemy in self.enemies[:]:
            enemy.update(dt, self.player, self.tcod_map)

        for projectile in self.projectiles[:]:
            projectile.update(dt, self.enemies, self)

        for explosion in self.explosions[:]:
            explosion.update(dt, self.enemies, self)
            if not explosion.active:
                self.explosions.remove(explosion)

        for boss in self.bosses[:]:
            boss.update(dt, self.player, self.tcod_map)
            if boss.health <= 0:
                self.defeat_boss(boss)

        if self.time_elapsed >= 900:
            self.end_game()

    def handle_events(self, dt):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_a]:
            self.player.move("left", self.tcod_map, dt)
        if keys[pygame.K_d]:
            self.player.move("right", self.tcod_map, dt)
        if keys[pygame.K_w]:
            self.player.move("up", self.tcod_map, dt)
        if keys[pygame.K_s]:
            self.player.move("down", self.tcod_map, dt)
        if keys[pygame.K_q]:
            self.player.fire_explosion(self.time_elapsed, self.explosions)
        if keys[pygame.K_e]:
            self.player.fire_electric_burst(self.projectiles, self.enemies, self.explosions, self.time_elapsed)

    def spawn_enemies(self, count):
        for _ in range(count):
            x, y = random.randint(0, MAP_WIDTH - 1), random.randint(0, MAP_HEIGHT - 1)
            while x == self.player.position[0] and y == self.player.position[1]:
                x, y = random.randint(0, MAP_WIDTH - 1), random.randint(0, MAP_HEIGHT - 1)
            enemy = Enemy([x, y])
            print(f"Spawned enemy at {x}, {y} with health {enemy.health}")
            self.enemies.append(enemy)

    def spawn_boss_wave(self):
        x, y = random.randint(0, MAP_WIDTH - 1), random.randint(0, MAP_HEIGHT - 1)
        while x == self.player.position[0] and y == self.player.position[1]:
            x, y = random.randint(0, MAP_WIDTH - 1), random.randint(0, MAP_HEIGHT - 1)
        self.bosses.append(Boss([x, y]))

    def end_game(self):
        self.game_over = True
        print(f"Game Over! Score: {self.score}")

class Player:
    def __init__(self, class_type, position):
        self.class_type = class_type
        self.position = position
        self.health = 100
        self.mana = 100
        self.speed = 30  # Tiles per second (adjusted for dt)
        self.last_shot_time = 0
        self.last_explosion_time = 0
        self.explosion_cooldown = 1
        self.explosions = []
        self.last_electric_burst_time = 0
        self.electric_burst_cooldown = 1
        self.frames = [pygame.image.load(f"Player/player ({i}).gif") for i in range(1, 14)]
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.1

    def move(self, direction, tcod_map, dt):
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}.get(direction, (0, 0))
        new_x = self.position[0] + dx * self.speed * dt
        new_y = self.position[1] + dy * self.speed * dt
        if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and tcod_map.walkable[int(new_y), int(new_x)]):
            self.position[0] = new_x
            self.position[1] = new_y

    def update(self, dt):
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

    def attack(self, projectiles, enemies, time_elapsed):
        if not enemies:
            return

        if time_elapsed - self.last_shot_time >= 1:
            self.last_shot_time = time_elapsed
            closest_enemy = min(enemies, key=lambda e: (e.position[0] - self.position[0])**2 + (e.position[1] - self.position[1])**2)
            direction_x = closest_enemy.position[0] - self.position[0]
            direction_y = closest_enemy.position[1] - self.position[1]
            magnitude = (direction_x**2 + direction_y**2) ** 0.5
            if magnitude != 0:
                direction_x /= magnitude
                direction_y /= magnitude
            projectile = Projectile(list(self.position), (direction_x, direction_y), 26)
            projectiles.append(projectile)
            print(f"Projectile fired at enemy at {closest_enemy.position}")

    def fire_explosion(self, time_elapsed, explosions_list):
        if time_elapsed - self.last_explosion_time >= self.explosion_cooldown:
            self.last_explosion_time = time_elapsed
            explosion = FireExplosion(list(self.position))
            explosions_list.append(explosion)
            print(f"Fire explosion triggered at {self.position}")

    def fire_electric_burst(self, projectiles, enemies, explosions, time_elapsed):
        if not enemies:
            return

        if time_elapsed - self.last_electric_burst_time >= self.electric_burst_cooldown:
            self.last_electric_burst_time = time_elapsed
            closest_enemy = min(enemies, key=lambda e: (e.position[0] - self.position[0])**2 + (e.position[1] - self.position[1])**2)
            direction_x = closest_enemy.position[0] - self.position[0]
            direction_y = closest_enemy.position[1] - self.position[1]
            magnitude = (direction_x**2 + direction_y**2) ** 0.5
            if magnitude != 0:
                direction_x /= magnitude
                direction_y /= magnitude
                projectile = ElectricBurst(list(self.position), (direction_x, direction_y), 26)
                print(f"Electric Burst fired at enemy at {closest_enemy.position}")
                projectiles.append(projectile)

class AbstractEnemy:
    def __init__(self, position):
        self.position = position
        self.health = 200
        self.speed = 0.6
        self.frames = []
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.2
        self.facing_right = True
        self.scale_factor = 4

    def move(self, player, tcod_map, dt):
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

        self.position[0] += dx * self.speed * dt
        self.position[1] += dy * self.speed * dt

    def attack(self, player):
        if abs(self.position[0] - player.position[0]) < 1 and abs(self.position[1] - player.position[1]) < 1:
            player.health -= 5
            print(f"Enemy attacked player! Player health: {player.health}")

    def take_damage(self, amount):
        self.health -= amount
        print(f"Enemy took {amount} damage! Remaining health: {self.health}")
        if self.health <= 0:
            print("Enemy has been defeated.")

    def update(self, dt, player, tcod_map):
        self.move(player, tcod_map, dt)
        self.attack(player)
        self.frame_timer += dt
        if self.frame_timer >= self.frame_duration and self.frames:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

    def draw(self, screen):
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        if self.frames and self.current_frame < len(self.frames):
            frame = self.frames[self.current_frame]
            scaled_size = TILE_SIZE * self.scale_factor
            frame = pygame.transform.scale(frame, (scaled_size, scaled_size))
            if not self.facing_right:
                frame = pygame.transform.flip(frame, True, False)
            screen.blit(frame, (screen_x - scaled_size // 2, screen_y - scaled_size // 2))
        else:
            print(f"Error in AbstractEnemy.draw: current_frame={self.current_frame}, frames_len={len(self.frames)}")

class Enemy(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)
        try:
            self.frames = [pygame.image.load(f"Enemies/Enemy ({i}).gif") for i in range(1, 6)]
            if not self.frames:
                raise ValueError("No enemy frames loaded")
            print(f"Loaded {len(self.frames)} normal frames")
        except (pygame.error, FileNotFoundError, ValueError) as e:
            print(f"Error loading enemy frames: {e}")
            self.frames = [pygame.Surface((32, 32)) for _ in range(5)]
            for surface in self.frames:
                surface.fill((255, 0, 0))
        self.scale_factor = 12

class Boss(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)
        self.health = 400
        self.frames = [pygame.image.load(f"Enemies/Enemy ({i}).gif") for i in range(1, 6)]
        self.scale_factor = 24

class FireExplosion:
    def __init__(self, position, radius=12, damage=40):
        self.position = position
        self.radius = radius
        self.damage = damage
        self.frames = [pygame.image.load(f"Explosion/Explosion{i}.png") for i in range(9, 17)]
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
                    if enemy.health <= 0 and game_manager:
                        game_manager.defeat_enemy(enemy)
                        print(f"Fire explosion hit enemy at {enemy.position}, dealt {self.damage} damage")

    def draw(self, screen):
        if not self.active:
            return
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        scaled_size = int(self.radius * TILE_SIZE * 2)
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
                if enemy.health <= 0 and game_manager:
                    game_manager.defeat_enemy(enemy)

        self.frame_timer += dt * 10
        if self.frame_timer >= 1:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.frame_timer = 0

    def draw(self, screen):
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        frame = self.rotated_frames[self.current_frame]
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class ElectricBurst(Projectile):
    def __init__(self, position, direction, damage):
        super().__init__(position, direction, damage)
        self.speed = 5
        self.frames = [pygame.image.load(f"ElectricBurst/electricburst ({i}).png") for i in range(1, 16)]
        self.current_frame = 0
        self.frame_timer = 0
        self.frame_duration = 0.2
        self.active = True
        self.aoe_range = 3
        self.aoe_damage = 40
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
                    if enemy.health <= 0 and game_manager:
                        game_manager.defeat_enemy(enemy)
                        print(f"Enemy at {enemy.position} defeated by Electric Burst")
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
            print(f"Electric Burst dispersed at {self.position}")

        if (self.position[0] < 0 or self.position[0] >= MAP_WIDTH or
            self.position[1] < 0 or self.position[1] >= MAP_HEIGHT):
            self.active = False

    def draw(self, screen):
        if not self.active:
            return
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        frame = self.frames[self.current_frame]
        original_size = frame.get_size()
        scaled_size = (int(original_size[0] * 3), int(original_size[1] * 3))
        frame = pygame.transform.scale(frame, scaled_size)
        rect = frame.get_rect(center=(int(screen_x), int(screen_y)))
        screen.blit(frame, rect)

class ExpOrb:
    def __init__(self, position, value=50):
        self.position = position
        self.value = value
        self.radius = 4  # Pixels
        self.color = (0, 0, 255)  # Blue

    def draw(self, screen):
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        pygame.draw.circle(screen, self.color, (screen_x, screen_y), self.radius)

def map_to_screen(x, y):
    return int(x * TILE_SIZE), int(y * TILE_SIZE)

def draw_map(screen, tcod_map):
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            color = (100, 100, 100) if tcod_map.walkable[y, x] else (0, 0, 0)
            pygame.draw.rect(screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Arcane Conquest")

    background_image = pygame.image.load("Background/background1.png")
    background_image = pygame.transform.scale(background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))

    game_manager = GameManager()
    game_manager.start_game()

    clock = pygame.time.Clock()

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        font = pygame.font.SysFont(None, 48)

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        game_manager.handle_events(dt)
        game_manager.update(dt)

        screen.fill((0, 0, 0))
        screen.blit(background_image, (0, 0))

        score_text = font.render(f"Score: {game_manager.score}", True, (255, 255, 255))
        wave_text = font.render(f"Wave: {game_manager.current_wave}", True, (255, 255, 255))
        screen.blit(score_text, (10, 10))
        screen.blit(wave_text, (10, 50))

        player_x, player_y = map_to_screen(*game_manager.player.position)
        frame = game_manager.player.frames[game_manager.player.current_frame]
        scaled_size = TILE_SIZE * 4
        frame = pygame.transform.scale(frame, (scaled_size, scaled_size))
        screen.blit(frame, (player_x - scaled_size // 2, player_y - scaled_size // 2))

        health_bar_width = TILE_SIZE * 4
        health_bar_height = 5
        health_percentage = game_manager.player.health / 100
        filled_width = health_bar_width * health_percentage
        health_bar_x = player_x - (health_bar_width // 2)
        health_bar_y = player_y + (TILE_SIZE * 4) // 2 + 2
        pygame.draw.rect(screen, (255, 0, 0), (health_bar_x, health_bar_y, health_bar_width, health_bar_height))
        pygame.draw.rect(screen, (0, 255, 0), (health_bar_x, health_bar_y, filled_width, health_bar_height))

        for enemy in game_manager.enemies:
            enemy.draw(screen)

        for item in game_manager.items:
            item.draw(screen)

        for boss in game_manager.bosses:
            boss.draw(screen)

        for projectile in game_manager.projectiles[:]:
            projectile.draw(screen)

        for explosion in game_manager.explosions[:]:
            explosion.draw(screen)

        if game_manager.game_over:
            game_over_text = font.render("Game Over", True, (255, 0, 0))
            score_text = font.render(f"Score: {game_manager.score}", True, (255, 255, 255))
            text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20))
            screen.blit(game_over_text, text_rect)
            screen.blit(score_text, score_rect)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()