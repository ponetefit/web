import pygame
import math
import time
import random

# --- CONFIGURACIÓN GLOBAL INICIAL ---
# Usamos flags para que la ventana sea redimensionable
WIDTH, HEIGHT = 1200, 800
FPS = 60

# Colores de UI y Efectos
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 50, 50)
BLUE = (50, 100, 255)
GREEN = (50, 255, 100)
YELLOW = (255, 255, 0)

# --- CONFIGURACIÓN DE CONTROLES ---
PLAYER_CONTROLS = [
    {'acc': pygame.K_a, 'brk': pygame.K_s, 'rst': pygame.K_d, 'color': RED, 'name': 'GT-RED'},
    {'acc': pygame.K_UP, 'brk': pygame.K_DOWN, 'rst': pygame.K_RIGHT, 'color': BLUE, 'name': 'FORMULA-BLUE'},
    {'acc': pygame.K_j, 'brk': pygame.K_k, 'rst': pygame.K_l, 'color': GREEN, 'name': 'VIPER-GREEN'},
    {'acc': pygame.K_KP8, 'brk': pygame.K_KP5, 'rst': pygame.K_KP6, 'color': YELLOW, 'name': 'BUMBLE-BEE'}
]

# --- COORDENADAS NORMALIZADAS (0.0 a 1.0) ---
# Esto permite que la pista sea responsive
TRACK_RAW = [
    (0.11, 0.32), (0.23, 0.27), (0.40, 0.22), (0.69, 0.15), (0.87, 0.14), 
    (0.94, 0.21), (0.95, 0.85), (0.86, 0.98), (0.69, 0.95), (0.62, 0.79), 
    (0.71, 0.60), (0.70, 0.49), (0.53, 0.64), (0.51, 0.80), (0.38, 0.98), 
    (0.21, 0.97), (0.11, 0.79), (0.18, 0.68), (0.39, 0.67), (0.42, 0.54), 
    (0.26, 0.51), (0.12, 0.52), (0.09, 0.43)
]

# --- CLASES DE EFECTOS ---

class Particle:
    def __init__(self, pos, color, life=20):
        self.pos = list(pos)
        self.vel = [random.uniform(-1, 1), random.uniform(-1, 1)]
        self.life = life
        self.color = color

    def update(self):
        self.pos[0] += self.vel[0]
        self.pos[1] += self.vel[1]
        self.life -= 1

    def draw(self, surface):
        if self.life > 0:
            alpha = min(255, self.life * 12)
            s = pygame.Surface((4, 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color[:3], alpha), (2, 2), 2)
            surface.blit(s, self.pos)

# --- CLASES PRINCIPALES ---

class Circuit:
    def __init__(self, normalized_points):
        self.normalized_points = normalized_points
        self.points = []
        self.is_closed = True

    def update_resolution(self, w, h):
        """Recalcula los puntos físicos según la resolución actual."""
        self.points = [(p[0] * w, p[1] * h) for p in self.normalized_points]

    def draw(self, surface, num_players):
        # Rieles técnicos sutiles
        for i in range(num_players):
            offset_points = self.get_offset_points(i, num_players)
            if len(offset_points) > 1:
                pygame.draw.lines(surface, (30, 30, 30), self.is_closed, offset_points, 1)
        
        # Línea de meta
        if len(self.points) > 1:
            p1, p2 = self.points[0], self.points[1]
            pygame.draw.line(surface, WHITE, p1, p2, 4)

    def get_offset_points(self, player_idx, total_players):
        # El ancho del carril también debería escalar ligeramente con la resolución
        scale_factor = (pygame.display.get_surface().get_width() / 1200)
        offset_dist = (player_idx - (total_players - 1) / 2) * (22 * scale_factor)
        
        new_points = []
        for i in range(len(self.points)):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % len(self.points)]
            dx, dy = p2[0] - p1[0], p2[1] - p1[1]
            mag = math.hypot(dx, dy) or 1
            nx, ny = -dy / mag, dx / mag
            new_points.append((p1[0] + nx * offset_dist, p1[1] + ny * offset_dist))
        return new_points

class Car:
    def __init__(self, player_idx, controls):
        self.player_idx = player_idx
        self.controls = controls
        self.color = controls['color']
        self.name = controls['name']
        self.particles = []
        self.skidmarks = []
        self.reset_state()
        
    def reset_state(self):
        self.index, self.sub_pos, self.speed = 0, 0.0, 0.0
        self.max_speed = 15.0
        self.acceleration = 0.22
        self.friction = 0.07
        self.on_rail = True
        self.last_pos = [0, 0]
        self.angle, self.laps = 0, 0
        self.shake_amount = 0

    def update(self, circuit, total_players):
        keys = pygame.key.get_pressed()
        player_track = circuit.get_offset_points(self.player_idx, total_players)

        if self.on_rail:
            if keys[self.controls['acc']]: 
                self.speed += self.acceleration
                if self.speed > self.max_speed * 0.7:
                    self.particles.append(Particle(self.last_pos, (255,255,255), 8))
            elif keys[self.controls['brk']]: 
                self.speed -= self.acceleration * 3.5
                if self.speed > 4:
                    self.skidmarks.append((list(self.last_pos), self.angle))
            else:
                self.speed -= self.friction
            
            self.speed = max(min(self.speed, self.max_speed), 0)

            if len(player_track) > 1:
                p1 = player_track[self.index]
                p2 = player_track[(self.index + 1) % len(player_track)]
                dist = math.hypot(p2[0]-p1[0], p2[1]-p1[1]) or 1
                self.sub_pos += self.speed / dist

                if self.sub_pos >= 1.0:
                    self.sub_pos = 0.0
                    self.index = (self.index + 1) % len(player_track)
                    if self.index == 0: self.laps += 1
                
                self.last_pos = [p1[0] + (p2[0] - p1[0]) * self.sub_pos, p1[1] + (p2[1] - p1[1]) * self.sub_pos]
                self.angle = math.degrees(math.atan2(p1[1] - p2[1], p2[0] - p1[0]))

                # Límite de adherencia
                if self.speed > 4.0:
                    p0 = player_track[(self.index - 1) % len(player_track)]
                    a1 = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
                    a0 = math.atan2(p1[1]-p0[1], p1[0]-p0[0])
                    force = abs(self.speed) * abs(math.atan2(math.sin(a1-a0), math.cos(a1-a0)))
                    if force > 1.95:
                        self.on_rail = False
                        self.shake_amount = 12
        else:
            self.particles.append(Particle(self.last_pos, (120, 120, 120), 20))
            if keys[self.controls['rst']]:
                self.on_rail, self.speed = True, 0

        for p in self.particles[:]:
            p.update()
            if p.life <= 0: self.particles.remove(p)
        
        if len(self.skidmarks) > 40: self.skidmarks.pop(0)
        if self.shake_amount > 0: self.shake_amount -= 1

    def draw(self, surface):
        # Escalar tamaño visual según resolución
        win_w = surface.get_width()
        scale = win_w / 1200
        w, h = 28 * scale, 14 * scale

        for pos, ang in self.skidmarks:
            s = pygame.Surface((10 * scale, 2 * scale), pygame.SRCALPHA)
            s.fill((0, 0, 0, 60))
            surface.blit(pygame.transform.rotate(s, ang), pos)

        for p in self.particles: p.draw(surface)

        if not self.last_pos: return
        
        # Sombra
        shadow_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 80), (0, 0, w, h), border_radius=int(4*scale))
        rotated_shadow = pygame.transform.rotate(shadow_surf, self.angle)
        surface.blit(rotated_shadow, rotated_shadow.get_rect(center=(self.last_pos[0]+3*scale, self.last_pos[1]+3*scale)))

        # Coche
        car_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(car_surf, self.color, (0, 0, w, h), border_radius=int(4*scale))
        pygame.draw.rect(car_surf, (255,255,255, 120), (2*scale, 2*scale, w-4*scale, 2*scale)) # Brillo
        pygame.draw.rect(car_surf, (20, 20, 20), (w//3, h//4, w//3, h//2), border_radius=int(2*scale)) # Cabina
        
        if not self.on_rail: car_surf.set_alpha(150)
        rotated = pygame.transform.rotate(car_surf, self.angle)
        
        pos = list(self.last_pos)
        if self.shake_amount > 0:
            pos[0] += random.randint(-2, 2)
            pos[1] += random.randint(-2, 2)

        surface.blit(rotated, rotated.get_rect(center=pos))

# --- BUCLE PRINCIPAL ---

def main():
    pygame.init()
    # Inicializamos con modo RESIZABLE
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Scalextric Pro Responsive")
    clock = pygame.time.Clock()
    
    # Carga de Imagen
    bg_raw = None
    bg_scaled = None
    try:
        bg_raw = pygame.image.load("image_8acf7e.jpg").convert()
    except:
        pass

    def scale_background(w, h):
        if bg_raw:
            return pygame.transform.scale(bg_raw, (w, h))
        return None

    circuit = Circuit(TRACK_RAW)
    circuit.update_resolution(WIDTH, HEIGHT)
    bg_scaled = scale_background(WIDTH, HEIGHT)
    
    players = []
    mode = "MENU"
    num_players = 1

    while True:
        curr_w, curr_h = screen.get_size()
        
        # Gestión de Eventos
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            
            if event.type == pygame.VIDEORESIZE:
                # La ventana cambió de tamaño
                new_w, new_h = event.w, event.h
                screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                circuit.update_resolution(new_w, new_h)
                bg_scaled = scale_background(new_w, new_h)

            if event.type == pygame.KEYDOWN:
                if mode == "MENU":
                    if event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4]:
                        num_players = int(event.unicode)
                        players = [Car(i, PLAYER_CONTROLS[i]) for i in range(num_players)]
                        mode = "CARRERA"
                elif mode == "CARRERA":
                    if event.key == pygame.K_ESCAPE:
                        mode = "MENU"

        # --- DIBUJO ---
        if mode == "MENU":
            screen.fill((25, 30, 35))
            font_size = int(curr_w / 15)
            font_big = pygame.font.SysFont("Impact", font_size)
            font_small = pygame.font.SysFont("Verdana", int(curr_w / 50), bold=True)
            
            title = font_big.render("GT RACING PRO", True, WHITE)
            screen.blit(title, (curr_w//2 - title.get_width()//2, curr_h * 0.2))
            
            hint = font_small.render("PRESIONE [1-4] PARA EMPEZAR", True, YELLOW)
            screen.blit(hint, (curr_w//2 - hint.get_width()//2, curr_h * 0.5))
            
            controls_info = font_small.render("ESC para salir | R/KP6/D/L para reentrar", True, (150, 150, 150))
            screen.blit(controls_info, (curr_w//2 - controls_info.get_width()//2, curr_h * 0.8))

        elif mode == "CARRERA":
            if bg_scaled:
                screen.blit(bg_scaled, (0, 0))
            else:
                screen.fill((40, 70, 40))

            circuit.draw(screen, num_players)
            
            for p in players:
                p.update(circuit, num_players)
                p.draw(screen)

            # HUD Responsive
            hud_font = pygame.font.SysFont("Verdana", int(curr_w / 65), bold=True)
            for i, p in enumerate(players):
                # Barra de Velocidad
                bar_w = int(curr_w * 0.12)
                bar_h = int(curr_h * 0.012)
                speed_pct = abs(p.speed / p.max_speed)
                
                start_x, start_y = 20, 20 + i * (curr_h * 0.06)
                pygame.draw.rect(screen, (30, 30, 30, 150), (start_x, start_y, bar_w, bar_h))
                pygame.draw.rect(screen, p.color, (start_x, start_y, bar_w * speed_pct, bar_h))
                
                info = f"{p.name} - LAP {p.laps}"
                if not p.on_rail: info += " [OFF TRACK]"
                txt = hud_font.render(info, True, WHITE)
                screen.blit(txt, (start_x, start_y + bar_h + 5))

        pygame.display.flip()
        clock.tick(FPS)

if __name__ == "__main__":
    main()
