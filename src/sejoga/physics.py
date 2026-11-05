"""
ScreenSpacePhysics — Física 2D em espaço de tela (pixels) para o desktop companion.

Implementa:
- Espaço pymunk 2D em coordenadas de tela (y para baixo)
- Passo fixo 1/120s com acumulador
- EnumWindows + DwmGetWindowAttribute para detectar janelas como "prateleiras" (shelves)
- One-way shelves: só a aresta superior colide, só quando descendo (y > 0)
- Arremesso: drag → KINEMATIC → release → DYNAMIC + velocity clamp
- Corpo do mascote: pymunk.Circle com elasticidade, friction, damping
- Gravidade 0 no modo "flutuando"; gravidade > 0 só quando caindo/quicando
- Amortecimento: space.damping aplicado por step
- Velocidade máxima limitada (~3200 px/s) para evitar tunneling
- Refresh de janelas: cache 250-400ms só enquanto mascote se move
- DPI awareness: PER_MONITOR_AWARE_V2 antes de criar janelas
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Callable
from collections import deque

import pymunk
# import pymunk.pygame_util  # para debug draw se necessário (removido - requer pygame)

# Win32 para detecção de janelas
import win32gui
import win32con
import win32api
import win32process
import ctypes
from ctypes import wintypes

# Project imports
from .rig import Rig
from .config import Settings, load_settings

# ============================================================
# Constantes e Configuração
# ============================================================

# Categorias de colisão (bitmasks)
CAT_MASCOT = 0b0001
CAT_SHELF = 0b0010
CAT_SCREEN_EDGE = 0b0100

# Física
FIXED_DT = 1.0 / 120.0  # 120 Hz physics step
MAX_SUBSTEPS = 4
MAX_VELOCITY = 3200.0  # px/s - clamp para evitar tunneling
DEFAULT_GRAVITY = 2400.0  # px/s² quando caindo
DRAG = 0.995  # damping per step (0.995^120 ≈ 0.55/s)
WALL_THICKNESS = 2  # pixels

# Janelas
SHELF_CACHE_TTL = 0.3  # segundos - cache de prateleiras
SHELF_REFRESH_DISTANCE = 200  # px - só refresh se mascote a < 200px de janela

# DPI
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except Exception:
    pass

# ============================================================
# Estruturas de Dados
# ============================================================

@dataclass
class Shelf:
    """Representa uma 'prateleira' (borda superior de uma janela)."""
    hwnd: int
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom) - coordenadas de tela
    top_y: int  # Y da borda superior (y para baixo = menor valor = mais alto)
    left: int
    right: int
    
    @property
    def width(self) -> int:
        return self.right - self.left
    
    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0


@dataclass
class PhysicsState:
    """Estado atual da física para debug/sync."""
    position: Tuple[float, float]  # (x, y) centro do corpo
    velocity: Tuple[float, float]  # (vx, vy) px/s
    grounded: bool
    on_shelf: Optional[int] = None  # hwnd da shelf atual
    gravity_active: bool = False
    sleep_timer: float = 0.0


# ============================================================
# Utilitários Win32 para EnumWindows / DwmGetWindowAttribute
# ============================================================

# DwmGetWindowAttribute constants
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14

dwmapi = ctypes.windll.dwmapi
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.c_void_p,
    wintypes.DWORD
]

def frame_bounds(hwnd: int) -> Tuple[int, int, int, int]:
    """Retorna bounds reais da janela (extended frame bounds) via DWM."""
    rect = wintypes.RECT()
    result = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_EXTENDED_FRAME_BOUNDS,
        ctypes.byref(rect),
        ctypes.sizeof(rect)
    )
    if result == 0:
        return (rect.left, rect.top, rect.right, rect.bottom)
    # Fallback para GetWindowRect
    return win32gui.GetWindowRect(hwnd)

def cloaked(hwnd: int) -> bool:
    """Verifica se janela está cloaked (minimizada/UWP oculta)."""
    v = wintypes.DWORD()
    result = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        DWMWA_CLOAKED,
        ctypes.byref(v),
        ctypes.sizeof(v)
    )
    return result == 0 and bool(v.value)


def is_valid_shelf(hwnd: int, own_pid: int) -> bool:
    """Verifica se janela é uma shelf válida (visível, não cloaked, não toolwindow, não próprio)."""
    if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        return False
    if win32gui.GetClassName(hwnd) in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return False
    if cloaked(hwnd) or not win32gui.GetWindowText(hwnd):
        return False
    
    # Filtra toolwindows e janelas sem título
    ex_style = win32gui.GetWindowLong(hwnd, -20)  # GWL_EXSTYLE
    if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
        return False
    
    # Filtra própria janela
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid == own_pid:
        return False
    
    # Área mínima
    rect = frame_bounds(hwnd)
    if (rect[2] - rect[0]) < 50 or (rect[3] - rect[1]) < 30:
        return False
    
    return True


def get_all_shelves(own_hwnd: int, own_pid: int) -> List[Shelf]:
    """Enumera todas as janelas válidas e retorna lista de Shelves."""
    shelves = []
    
    def enum_callback(hwnd: int, _: int) -> bool:
        try:
            if is_valid_shelf(hwnd, own_pid):
                rect = frame_bounds(hwnd)
                shelves.append(Shelf(hwnd, rect, rect[1], rect[0], rect[2]))
        except win32gui.error:
            # Another application's HWND can disappear during enumeration.
            pass
        return True
    
    win32gui.EnumWindows(enum_callback, 0)
    # EnumWindows is front-to-back. Only exposed portions of a window's top
    # edge can support the mascot; hidden windows must not create air shelves.
    visible = []
    for index, shelf in enumerate(shelves):
        spans = [(shelf.left, shelf.right)]
        for front in shelves[:index]:
            if front.rect[1] <= shelf.top_y < front.rect[3]:
                spans = [(a, b) for left, right in spans
                         for a, b in ((left, min(right, front.left)), (max(left, front.right), right))
                         if b - a > 2]
        for left, right in spans:
            visible.append(Shelf(shelf.hwnd, shelf.rect, shelf.top_y, left, right))
    return visible


# ============================================================
# ScreenSpacePhysics - Classe Principal
# ============================================================

class ScreenSpacePhysics:
    """
    Gerencia física 2D em espaço de tela para o mascote.
    
    Responsabilidades:
    - Manter espaço pymunk sincronizado com janelas do desktop
    - Simular física do mascote (gravidade, colisão, arraste/arremesso)
    - Atualizar cache de prateleiras (janelas) periodicamente
    - Fornecer estado de física para animação/render
    """
    
    def __init__(
        self,
        mascot_radius: float = 40.0,
        screen_width: int = 1920,
        screen_height: int = 1080,
        own_hwnd: int = 0,
        own_pid: int = 0,
        settings: Optional[Settings] = None
    ):
        self.mascot_radius = mascot_radius
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.own_hwnd = own_hwnd
        self.own_pid = own_pid
        self.settings = settings or load_settings()
        
        # Physics space
        self.space = pymunk.Space()
        self.space.gravity = (0, 0)  # Inicialmente sem gravidade (flutuando)
        self.space.damping = DRAG  # 0.995 per step
        
        # Pymunk 7 replaced add_collision_handler() with on_collision().
        if hasattr(self.space, "on_collision"):
            self.space.on_collision(
                CAT_MASCOT, CAT_SHELF, pre_solve=self._shelf_pre_solve
            )
            self.space.on_collision(
                CAT_MASCOT, CAT_SCREEN_EDGE, pre_solve=self._edge_pre_solve
            )
        else:
            self.space.add_collision_handler(
                CAT_MASCOT, CAT_SHELF
            ).pre_solve = self._shelf_pre_solve
            self.space.add_collision_handler(
                CAT_MASCOT, CAT_SCREEN_EDGE
            ).pre_solve = self._edge_pre_solve
        
        # State
        self.state = PhysicsState(
            position=(screen_width / 2, screen_height - mascot_radius - 10),
            velocity=(0, 0),
            grounded=False
        )

        # Mascot body needs the initial state position.
        self._create_mascot_body()

        # Screen edges (paredes da tela)
        self._create_screen_edges()

        # Shelves (janelas)
        self.shelves: List[Shelf] = []
        self.shelf_shapes: dict[int, pymunk.Segment] = {}  # hwnd -> shape
        self.shelf_cache_time = 0.0
        
        # Drag/throw state
        self._drag_active = False
        self._drag_samples: deque[Tuple[float, float, float]] = deque(maxlen=10)  # (t, x, y)
        self._drag_body_type = pymunk.Body.DYNAMIC
        
        # Physics step accumulator
        self._accumulator = 0.0
        
        # Callbacks
        self.on_state_change: Optional[Callable[[PhysicsState], None]] = None
        self.on_collision: Optional[Callable[[str, Tuple[float, float]], None]] = None
        
        # Cache
        self._shelf_cache_ttl = SHELF_CACHE_TTL
        self._last_shelf_refresh = 0.0
    
    def _create_mascot_body(self) -> None:
        """Cria corpo físico do mascote (circle)."""
        radius = self.mascot_radius
        mass = self.settings.physics.mass
        moment = pymunk.moment_for_circle(mass, 0, radius)
        
        self.body = pymunk.Body(mass, moment, body_type=pymunk.Body.DYNAMIC)
        self.body.position = self.state.position
        self.shape = pymunk.Circle(self.body, radius)
        self.shape.collision_type = CAT_MASCOT
        self.shape.elasticity = self.settings.physics.bounce
        self.shape.friction = self.settings.physics.friction
        self.shape.filter = pymunk.ShapeFilter(categories=CAT_MASCOT, mask=CAT_SHELF | CAT_SCREEN_EDGE)
        
        self.space.add(self.body, self.shape)
        
        # Sync initial state
        self.state.position = self.body.position
        self.state.velocity = self.body.velocity
    
    def _create_screen_edges(self) -> None:
        self.bounds = (0, 0, self.screen_width, self.screen_height)
        self._edges = []
        self.set_bounds(self.bounds)

    def set_bounds(self, bounds: tuple[int, int, int, int]) -> None:
        """Área útil do monitor, em coordenadas absolutas (inclusive negativas)."""
        if self._edges:
            self.space.remove(*self._edges)
        self.bounds = bounds
        left, top, right, bottom = bounds
        self._edges = []
        for a, b in (((left, bottom), (right, bottom)), ((left, top), (right, top)),
                     ((left, top), (left, bottom)), ((right, top), (right, bottom))):
            shape = pymunk.Segment(self.space.static_body, a, b, WALL_THICKNESS)
            shape.collision_type = CAT_SCREEN_EDGE
            shape.elasticity = 0.25
            shape.friction = 1.0
            shape.filter = pymunk.ShapeFilter(categories=CAT_SCREEN_EDGE, mask=CAT_MASCOT)
            self._edges.append(shape)
        self.space.add(*self._edges)
        self._bottom_shape = self._edges[0]

    def _shelf_pre_solve(self, arbiter, space, data) -> bool:
        shelf = next(shape for shape in arbiter.shapes if shape.collision_type == CAT_SHELF)
        # A rising body and a body approaching from underneath pass through.
        allowed = (self.body.velocity.y >= -1.0
                   and self.body.position.y + self.mascot_radius <= shelf.a.y + 6.0)
        if hasattr(arbiter, "process_collision"):
            arbiter.process_collision = allowed
        if allowed:
            self._contact_response(arbiter)
        return allowed

    def _edge_pre_solve(self, arbiter, space, data) -> bool:
        self._contact_response(arbiter)
        return True

    def _contact_response(self, arbiter) -> None:
        speed = self.body.velocity.length
        if speed < 160:
            arbiter.restitution = 0.0
        now = time.monotonic()
        if speed > 200 and now - getattr(self, "_last_impact", 0.0) > 0.2:
            self._last_impact = now
            if self.on_collision:
                self.on_collision("impact", tuple(self.body.velocity))

    def refresh_shelves(self, force: bool = False) -> None:
        """Atualiza cache de prateleiras (janelas)."""
        now = time.monotonic()
        if not force and (now - self._last_shelf_refresh) < self._shelf_cache_ttl:
            return
        
        self._last_shelf_refresh = now
        new_shelves = get_all_shelves(self.own_hwnd, self.own_pid)
        
        signature = lambda items: [(x.hwnd, x.left, x.right, x.top_y) for x in items]
        if signature(new_shelves) == signature(self.shelves):
            return
        if self.shelf_shapes:
            self.space.remove(*self.shelf_shapes.values())
        self.shelf_shapes.clear()
        for index, shelf in enumerate(new_shelves):
            shape = pymunk.Segment(self.space.static_body,
                                   (shelf.left, shelf.top_y), (shelf.right, shelf.top_y), WALL_THICKNESS)
            shape.collision_type = CAT_SHELF
            shape.elasticity = 0.25
            shape.friction = 1.0
            shape.filter = pymunk.ShapeFilter(categories=CAT_SHELF, mask=CAT_MASCOT)
            self.space.add(shape)
            key = shelf.hwnd if shelf.hwnd not in self.shelf_shapes else (shelf.hwnd, index)
            self.shelf_shapes[key] = shape
        self.shelves = new_shelves
    
    def get_shelf_under_point(self, x: float, y: float) -> Optional[Shelf]:
        """Retorna shelf diretamente abaixo do ponto (x, y), se houver."""
        for shelf in self.shelves:
            if shelf.left <= x <= shelf.right and shelf.top_y >= y:
                return shelf
        return None
    
    # ============================================================
    # Drag & Throw
    # ============================================================
    
    def start_drag(self, mouse_x: float, mouse_y: float) -> None:
        """Inicia arraste - corpo vira KINEMATIC."""
        if self._drag_active:
            return
        
        self._drag_active = True
        self._drag_offset = (self.body.position.x - mouse_x, self.body.position.y - mouse_y)
        self.state.grounded = False
        self.set_gravity(False)
        self._drag_samples.clear()
        self._record_drag_sample()
        
        # Corpo vira KINEMATIC durante drag (controlado pelo mouse)
        self.body.body_type = pymunk.Body.KINEMATIC
        self.body.velocity = (0, 0)
        self._drag_body_type = pymunk.Body.KINEMATIC
    
    def update_drag(self, mouse_x: float, mouse_y: float) -> None:
        """Atualiza posição durante drag."""
        if not self._drag_active:
            return
        
        self.body.position = (mouse_x + self._drag_offset[0], mouse_y + self._drag_offset[1])
        self.state.position = tuple(self.body.position)
        self._record_drag_sample()
        # Velocity será calculada no release baseado nos samples
    
    def end_drag(self, cancel: bool = False) -> Tuple[float, float]:
        """Finaliza arraste - calcula velocidade e volta a DYNAMIC."""
        if not self._drag_active:
            return (0, 0)
        
        self._drag_active = False
        self.body.body_type = pymunk.Body.DYNAMIC
        # Switching back from KINEMATIC resets mass/moment in Pymunk 7.
        mass = self.settings.physics.mass
        self.body.mass = mass
        self.body.moment = pymunk.moment_for_circle(mass, 0, self.mascot_radius)
        self.body.angular_velocity = 0.0
        
        # Estima velocidade dos últimos samples
        velocity = self._estimate_velocity_from_samples() if not cancel else (0.0, 0.0)
        velocity = tuple(v * self.settings.physics.throw_multiplier for v in velocity)
        
        # Clamp
        speed = math.hypot(velocity[0], velocity[1])
        if speed > MAX_VELOCITY:
            scale = MAX_VELOCITY / speed
            velocity = (velocity[0] * scale, velocity[1] * scale)
        
        self.body.velocity = velocity
        self._drag_body_type = pymunk.Body.DYNAMIC
        
        # Constrain a release to the selected monitor, keeping negative origins.
        left, top, right, bottom = self.bounds
        r = self.mascot_radius + WALL_THICKNESS
        self.body.position = (max(left+r, min(right-r, self.body.position.x)),
                              max(top+r, min(bottom-r, self.body.position.y)))
        self.state.position = tuple(self.body.position)
        self.state.velocity = velocity
        self.set_gravity(not cancel)
        
        return velocity
    
    def _record_drag_sample(self) -> None:
        """Registra posição/tempo atual para estimativa de velocidade."""
        now = time.monotonic()
        pos = self.body.position
        self._drag_samples.append((now, pos.x, pos.y))
    
    def _estimate_velocity_from_samples(self) -> Tuple[float, float]:
        """Estima velocidade baseada nos últimos samples (janela ~60ms)."""
        if len(self._drag_samples) < 2:
            return (0.0, 0.0)
        
        now = time.monotonic()
        # Usa samples dos últimos ~60ms
        recent = [(t, x, y) for t, x, y in self._drag_samples if now - t < 0.06]
        # No stale fallback: holding still before release must stop the throw.
        
        if len(recent) < 2:
            return (0.0, 0.0)
        
        # Velocidade média ponderada (mais peso pros recentes)
        vx = vy = 0.0
        total_weight = 0.0
        for i in range(1, len(recent)):
            t0, x0, y0 = recent[i-1]
            t1, x1, y1 = recent[i]
            dt = t1 - t0
            if dt <= 0:
                continue
            weight = (i / len(recent)) ** 2  # peso maior pros recentes
            vx += ((x1 - x0) / dt) * weight
            vy += ((y1 - y0) / dt) * weight
            total_weight += weight
        
        if total_weight == 0:
            return (0.0, 0.0)
        
        return (vx / total_weight, vy / total_weight)
    
    # ============================================================
    # Gravity / Grounded State
    # ============================================================
    
    def set_gravity(self, enabled: bool) -> None:
        """Ativa/desativa gravidade."""
        if enabled and self.space.gravity == (0, 0):
            self.space.gravity = (0, self.settings.physics.gravity if self.settings and self.settings.physics else DEFAULT_GRAVITY)
            self.state.gravity_active = True
        elif not enabled and self.space.gravity != (0, 0):
            self.space.gravity = (0, 0)
            self.state.gravity_active = False
    
    def update_grounded_state(self) -> None:
        was_grounded = self.state.grounded
        self.state.grounded = False
        self.state.on_shelf = None
        if not self._drag_active and abs(self.body.velocity.y) < 60:
            def contact(arbiter):
                if hasattr(arbiter, "process_collision") and not arbiter.process_collision:
                    return
                shapes = arbiter.shapes
                other = shapes[1] if shapes[0] == self.shape else shapes[0]
                normal = arbiter.contact_point_set.normal
                toward_floor = normal.y if shapes[0] == self.shape else -normal.y
                if toward_floor < 0.65 or not arbiter.contact_point_set.points:
                    return
                if other == self._bottom_shape:
                    self.state.grounded = True
                else:
                    for key, shape in self.shelf_shapes.items():
                        if other == shape:
                            self.state.grounded = True
                            self.state.on_shelf = key[0] if isinstance(key, tuple) else key
                            break
            self.body.each_arbiter(contact)
        if was_grounded and not self.state.grounded and not self._drag_active:
            self.set_gravity(True)
        self.state.gravity_active = bool(self.space.gravity.y) and not self.state.grounded

    def step(self, dt: float) -> PhysicsState:
        """Avança simulação por dt segundos."""
        if self.settings.physics.collide_with_windows:
            self.refresh_shelves()
        # Accumulator para step fixo
        self._accumulator += max(0.0, min(dt, 0.05))  # clamp dt
        while self._accumulator >= FIXED_DT:
            self.space.step(FIXED_DT)
            self._accumulator -= FIXED_DT
        
        
        # Update grounded state
        self.update_grounded_state()
        
        # Settle without Body.sleep(), which requires sleeping to be enabled.
        if self.state.grounded:
            vx = self.body.velocity.x * math.exp(-self.settings.physics.friction * 8 * dt)
            self.body.velocity = (0 if abs(vx) < 5 else vx, self.body.velocity.y)
        
        # Sync state
        self.state.position = (self.body.position.x, self.body.position.y)
        self.state.velocity = (self.body.velocity.x, self.body.velocity.y)
        
        # Callback
        if self.on_state_change:
            self.on_state_change(self.state)
        
        return self.state
    
    def set_position(self, x: float, y: float) -> None:
        """Define posição do mascote (teleport)."""
        self.body.position = (x, y)
        self.body.velocity = (0, 0)
        self.state.position = (x, y)
        self.state.velocity = (0, 0)
        self.state.grounded = False
        self.state.on_shelf = None
    
    def apply_impulse(self, impulse: Tuple[float, float]) -> None:
        """Aplica impulso instantâneo no centro de massa."""
        self.body.apply_impulse_at_world_point(impulse, self.body.position)
    
    def get_state(self) -> PhysicsState:
        return self.state
    
    def cleanup(self) -> None:
        """Limpeza."""
        self.space.remove(self.body, self.shape)
        for shape in self.shelf_shapes.values():
            self.space.remove(shape)
        self.space.remove(self._bottom_shape)
        # Screen edges são no static_body, não precisam remover individualmente


# ============================================================
# Função Factory
# ============================================================

def create_physics(
    mascot_radius: float = 40.0,
    screen_width: int = 1920,
    screen_height: int = 1080,
    own_hwnd: int = 0,
    own_pid: int = 0,
    settings: Optional[Settings] = None
) -> ScreenSpacePhysics:
    """Factory para criar ScreenSpacePhysics."""
    return ScreenSpacePhysics(
        mascot_radius=mascot_radius,
        screen_width=screen_width,
        screen_height=screen_height,
        own_hwnd=own_hwnd,
        own_pid=own_pid,
        settings=settings
    )


# ============================================================
# Debug Draw Helper (opcional)
# ============================================================

def debug_draw_space(space: pymunk.Space, surface) -> None:
    """Desenha debug do espaço pymunk (requer pygame)."""
    try:
        import pygame
        from pymunk.pygame_util import DrawOptions
        options = DrawOptions(surface)
        space.debug_draw(options)
    except ImportError:
        pass


if __name__ == "__main__":
    # Teste rápido
    import os
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    
    physics = create_physics(screen_width=800, screen_height=600)
    physics.state.position = (400, 300)
    physics.body.position = (400, 300)
    physics.set_gravity(True)
    
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        dt = 1/60
        state = physics.step(dt)
        
        screen.fill((20, 20, 30))
        debug_draw_space(physics.space, screen)
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()
