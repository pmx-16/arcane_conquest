import pygame
import tcod
import random

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
        self.current_wave = 0
        self.time_elapsed = 0
        self.wave_timer = 0
        self.score = 0
        self.game_over = False

    def start_game(self):
        self.current_wave = 1
        self.spawn_enemies(5)

    def update(self, dt):
        if self.game_over:
            return
        self.time_elapsed += dt

        # Spawn enemies every 10 seconds and limit the total number
        if self.time_elapsed - self.wave_timer >= 10 and len(self.enemies) < 10:
            self.spawn_enemies(1)
            self.wave_timer = self.time_elapsed

        # Ensure automatic shooting
        self.player.attack(self.projectiles, self.enemies, self.time_elapsed)

        # Update enemies
        for enemy in self.enemies[:]:
            enemy.update(dt, self.player, self.tcod_map)
            if enemy.health <= 0:
                self.enemies.remove(enemy)
                self.score += 10

        # Update projectiles
        for projectile in self.projectiles[:]:
            projectile.update(dt, self.enemies)


        for boss in self.bosses[:]:
            boss.update(dt, self.player, self.tcod_map)
            if boss.health <= 0:
                self.bosses.remove(boss)
                self.score += 50

        if self.time_elapsed >= 900:
            self.end_game()

    def handle_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.player.move("left", self.tcod_map)
                elif event.key == pygame.K_RIGHT:
                    self.player.move("right", self.tcod_map)
                elif event.key == pygame.K_UP:
                    self.player.move("up", self.tcod_map)
                elif event.key == pygame.K_DOWN:
                    self.player.move("down", self.tcod_map)
                elif event.key == pygame.K_SPACE:
                    self.player.attack(self.projectiles)

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
        self.last_shot_time = 0

    def move(self, direction, tcod_map):
        dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}.get(direction, (0, 0))
        new_x, new_y = self.position[0] + dx, self.position[1] + dy
        if (0 <= new_x < MAP_WIDTH and 0 <= new_y < MAP_HEIGHT and tcod_map.walkable[new_y, new_x]):
            self.position = [new_x, new_y]

    def update(self, dt):
        pass

    def attack(self, projectiles, enemies, time_elapsed):
        if not enemies:  # No enemies, no shooting
            return

        # Fire every 0.7 seconds(Testing)
        if time_elapsed - self.last_shot_time >= 0.7:
            self.last_shot_time = time_elapsed

            # Find the closest enemy
            closest_enemy = min(enemies, key=lambda e: (e.position[0] - self.position[0])**2 + (e.position[1] - self.position[1])**2)

            # Calculate direction towards enemy
            direction_x = closest_enemy.position[0] - self.position[0]
            direction_y = closest_enemy.position[1] - self.position[1]

            # Normalize direction
            magnitude = (direction_x**2 + direction_y**2) ** 0.5
            if magnitude != 0:
                direction_x /= magnitude
                direction_y /= magnitude

            # Create and fire projectile
            projectile = Projectile(list(self.position), (direction_x, direction_y), 17)  # 17 damage per shot
            projectiles.append(projectile)
            print(f"Projectile fired at enemy at {closest_enemy.position}")


class AbstractEnemy:
    def __init__(self, position):
        self.position = position
        self.health = 50
        self.speed = 0.2 #Slow speed for testing

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


class Enemy(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)


class Boss(AbstractEnemy):
    def __init__(self, position):
        super().__init__(position)
        self.health = 200


class Projectile:
    def __init__(self, position, direction, damage):
        self.position = position
        self.direction = direction
        self.damage = damage
        self.speed = 5

    def update(self, dt, enemies):
        self.position[0] += self.direction[0] * self.speed * dt
        self.position[1] += self.direction[1] * self.speed * dt

        for enemy in enemies[:]:
            if abs(enemy.position[0] - self.position[0]) < 1 and abs(enemy.position[1] - self.position[1]) < 1:
                enemy.take_damage(self.damage)
                if enemy.health <= 0:
                    enemies.remove(enemy)


    def draw(self, screen):
        screen_x, screen_y = map_to_screen(self.position[0], self.position[1])
        pygame.draw.circle(screen, (0, 255, 0), (int(screen_x), int(screen_y)), 5)  # Green projectile


def map_to_screen(x, y):
    return int(x * TILE_SIZE), int(y * TILE_SIZE)


def draw_map(screen, tcod_map):
    for x in range(MAP_WIDTH):
        for y in range(MAP_HEIGHT):
            color = (100, 100, 100) if tcod_map.walkable[y, x] else (0, 0, 0)
            pygame.draw.rect(screen, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))


def main():
    # Ensure Pygame is initialized
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Arcane Conquest")

    # Create the game manager
    game_manager = GameManager()

    # Start the game
    game_manager.start_game()

    # Initialize the clock for consistent frame rate
    clock = pygame.time.Clock()

    # Main game loop
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        # Handle user inputs
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        # Update game logic
        game_manager.handle_events(events)
        game_manager.update(dt)

        # Render the game state
        screen.fill((0, 0, 0))  # Clear the screen
        draw_map(screen, game_manager.tcod_map)

        # Draw player
        player_x, player_y = map_to_screen(*game_manager.player.position)
        pygame.draw.rect(screen, (0, 0, 255), (player_x, player_y, TILE_SIZE, TILE_SIZE))  # Blue Player

        # Draw enemies
        for enemy in game_manager.enemies:
            enemy_x, enemy_y = map_to_screen(*enemy.position)
            pygame.draw.rect(screen, (255, 0, 0), (enemy_x, enemy_y, TILE_SIZE * 2, TILE_SIZE * 2))  # Bigger enemy size

        # Draw bosses
        for boss in game_manager.bosses:
            boss_x, boss_y = map_to_screen(*boss.position)
            pygame.draw.rect(screen, (255, 165, 0), (boss_x, boss_y, TILE_SIZE * 2, TILE_SIZE * 2))  # Bigger boss size

        # Draw projectiles
        for projectile in game_manager.projectiles[:]:
            projectile.draw(screen)  # Green projectiles

        # Update the display
        pygame.display.flip()

    # Quit Pygame
    pygame.quit()

if __name__ == "__main__":
    main()