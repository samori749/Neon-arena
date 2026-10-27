"""
NEON FLIGHT 3D  -  настоящая 3D игра на чистом Python + tkinter
(только стандартная библиотека, ничего устанавливать не нужно)

Запуск:  python neon_flight_tkinter.py

Внутри свой 3D-движок: перспективная проекция, полигональные модели,
освещение по Ламберту, туман, отсечение задних граней, сортировка (алгоритм
художника), звёздное небо, частицы, тряска камеры.

Режимы:
  1. АСТЕРОИДЫ  - лети сквозь пояс астероидов, стреляй, уворачивайся от дронов
  2. ТОННЕЛЬ    - неоновый тоннель с воротами-препятствиями, скорость растёт
  3. КОЛЬЦА     - пролетай через кольца на время, копи комбо

Управление: WASD / стрелки - лететь, Пробел или ЛКМ - огонь,
            M - управление мышью, Esc - меню
"""
import tkinter as tk
import math
import random
import time
import json
import os
import colorsys

W, H = 1000, 620
CX, CY = W / 2, H / 2
FOC = 640.0
NEAR = 0.6
DRAW = 115.0
FOGS = 35.0
BG = (0.02, 0.02, 0.07)
POOL = 520
TL = 7.5            # половина ширины тоннеля
SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'neon_flight_scores.json')
HS = {'ast': 0, 'tun': 0, 'ring': 0}


def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def hexc(r, g, b):
    return '#%02x%02x%02x' % (int(255 * clamp(r, 0, 1)), int(255 * clamp(g, 0, 1)), int(255 * clamp(b, 0, 1)))


def hsv(h, s=1.0, v=1.0):
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


def norm(v):
    l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1
    return (v[0] / l, v[1] / l, v[2] / l)


LIGHT = norm((0.4, 0.8, -0.45))


def rotm(a, b, g):
    ca, sa, cb, sb, cg, sg = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(g), math.sin(g)
    return ((cg * cb, cg * sb * sa - sg * ca, cg * sb * ca + sg * sa),
            (sg * cb, sg * sb * sa + cg * ca, sg * sb * ca - cg * sa),
            (-sb, cb * sa, cb * ca))


class O:
    def __init__(self, **k):
        self.__dict__.update(k)


# ===================================================================
#  Модели
# ===================================================================
class Mesh:
    def __init__(self, verts, faces, lit=True, edge=None, bg=False):
        self.v = verts
        self.lit = lit
        self.edge = edge
        self.bg = bg
        n = len(verts)
        c = (sum(v[0] for v in verts) / n, sum(v[1] for v in verts) / n, sum(v[2] for v in verts) / n)
        self.faces = []
        for f in faces:
            idx, col = f[0], f[1]
            two = f[2] if len(f) > 2 else False
            a, b, d = verts[idx[0]], verts[idx[1]], verts[idx[2]]
            u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            w = (d[0] - a[0], d[1] - a[1], d[2] - a[2])
            nrm = norm((u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]))
            fc = (sum(verts[i][0] for i in idx) / len(idx) - c[0], sum(verts[i][1] for i in idx) / len(idx) - c[1],
                  sum(verts[i][2] for i in idx) / len(idx) - c[2])
            if nrm[0] * fc[0] + nrm[1] * fc[1] + nrm[2] * fc[2] < 0:
                nrm = (-nrm[0], -nrm[1], -nrm[2])
            self.faces.append((idx, col, two, nrm))


def make_box(col, edge=None):
    v = [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]
    f = [((0, 1, 2, 3), col), ((4, 5, 6, 7), col), ((0, 1, 5, 4), col),
         ((2, 3, 7, 6), col), ((1, 2, 6, 5), col), ((0, 3, 7, 4), col)]
    return Mesh(v, f, True, edge)


def make_asteroid(seed):
    r = random.Random(seed)
    p = (1 + 5 ** .5) / 2
    base = [(-1, p, 0), (1, p, 0), (-1, -p, 0), (1, -p, 0), (0, -1, p), (0, 1, p),
            (0, -1, -p), (0, 1, -p), (p, 0, -1), (p, 0, 1), (-p, 0, -1), (-p, 0, 1)]
    verts = []
    for v in base:
        n = norm(v)
        k = r.uniform(.72, 1.15)
        verts.append((n[0] * k, n[1] * k, n[2] * k))
    tri = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
           (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
           (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    faces = []
    for t in tri:
        k = r.uniform(.8, 1.15)
        faces.append((t, (.50 * k, .42 * k, .38 * k)))
    return Mesh(verts, faces, True, None)


def make_ship():
    v = [(0, 0, 2.0), (0, .45, .2), (-.55, 0, -.4), (.55, 0, -.4), (0, -.3, -.2), (0, .2, -1.0),
         (-1.7, -.1, -1.1), (1.7, -.1, -1.1), (-.45, 0, .5), (.45, 0, .5)]
    body, wing = (.62, .68, .82), (.18, .35, .65)
    f = [((0, 1, 2), body), ((0, 1, 3), body), ((0, 2, 4), body), ((0, 3, 4), body),
         ((1, 2, 5), body), ((1, 3, 5), body), ((2, 4, 5), body), ((3, 4, 5), body),
         ((8, 6, 2), wing, True), ((2, 6, 5), wing, True), ((9, 7, 3), wing, True), ((3, 7, 5), wing, True)]
    return Mesh(v, f, True, (.3, .9, 1.0))


def make_drone():
    v = [(0, 0, 1.4), (0, 0, -1.0), (1, 0, 0), (-1, 0, 0), (0, .6, 0), (0, -.6, 0), (-1.8, 0, -.6), (1.8, 0, -.6)]
    c = (.85, .15, .6)
    f = [((0, 2, 4), c), ((0, 4, 3), c), ((0, 3, 5), c), ((0, 5, 2), c),
         ((1, 4, 2), c), ((1, 3, 4), c), ((1, 5, 3), c), ((1, 2, 5), c),
         ((3, 6, 1), (.5, .1, .4), True), ((2, 7, 1), (.5, .1, .4), True)]
    return Mesh(v, f, True, (1.0, .5, .9))


def make_flame():
    v = [(-.28, 0, -1.0), (.28, 0, -1.0), (0, 0, -2.4), (0, -.28, -1.0), (0, .28, -1.0)]
    f = [((0, 1, 2), (1, .6, .2), True), ((3, 4, 2), (1, .8, .4), True)]
    return Mesh(v, f, False, None)


def make_bolt(col):
    v = [(-.14, 0, -1.2), (.14, 0, -1.2), (.14, 0, 1.2), (-.14, 0, 1.2),
         (0, -.14, -1.2), (0, .14, -1.2), (0, .14, 1.2), (0, -.14, 1.2)]
    return Mesh(v, [((0, 1, 2, 3), col, True), ((4, 5, 6, 7), col, True)], False, None)


def make_spark():
    return Mesh([(-1, -.8, 0), (1, -.8, 0), (0, 1, 0)], [((0, 1, 2), (1, 1, 1), True)], False, None)


def make_ring(r_out=4.6, r_in=3.5, n=8):
    v = []
    for i in range(n):
        a = 2 * math.pi * i / n
        v.append((math.cos(a) * r_out, math.sin(a) * r_out, 0))
        v.append((math.cos(a) * r_in, math.sin(a) * r_in, 0))
    f = []
    for i in range(n):
        j = (i + 1) % n
        f.append(((2 * i, 2 * j, 2 * j + 1, 2 * i + 1), (.9, .9, .9), True))
    return Mesh(v, f, False, (1, 1, 1))


def make_tunnel(sl=6.0):
    L = TL
    v = [(-L, -L, 0), (L, -L, 0), (L, -L, sl), (-L, -L, sl),
         (-L, L, 0), (L, L, 0), (L, L, sl), (-L, L, sl)]
    c = (.07, .07, .09)
    f = [((0, 1, 2, 3), c, True), ((4, 5, 6, 7), c, True), ((0, 4, 7, 3), c, True), ((1, 5, 6, 2), c, True)]
    return Mesh(v, f, False, (1, 1, 1), True)


SHIP, DRONE, FLAME = make_ship(), make_drone(), make_flame()
AST = [make_asteroid(i) for i in range(5)]
BOLT_P, BOLT_E = make_bolt((.4, 1, 1)), make_bolt((1, .3, .2))
SPARK, RING, TUNNEL = make_spark(), make_ring(), make_tunnel()
BOX = [make_box((.9, .9, .9), (1, 1, 1))]


# ===================================================================
#  3D-рендер на Canvas
# ===================================================================
def clip_near(pts):
    out = []
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ina, inb = a[2] >= NEAR, b[2] >= NEAR
        if ina:
            out.append(a)
        if ina != inb:
            t = (NEAR - a[2]) / (b[2] - a[2])
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, NEAR))
    return out


class Scene:
    def __init__(self, canvas):
        self.c = canvas
        self.pool = [canvas.create_polygon(0, 0, 0, 0, 0, 0, fill='#000000', outline='#000000', state='hidden')
                     for _ in range(POOL)]
        self.cache = [None] * POOL
        self.shown = 0
        self.faces = []
        self.cam = (0, 0, 0)
        self.cr, self.sr = 1.0, 0.0

    def begin(self, cam, roll):
        self.faces = []
        self.cam = cam
        self.cr, self.sr = math.cos(roll), math.sin(roll)

    def add(self, mesh, pos, rot=(0, 0, 0), sc=(1, 1, 1), tint=None):
        px, py, pz = pos
        cx, cy, cz = self.cam
        if pz - cz > DRAW + 10 or pz - cz < -10:
            return
        R = rotm(*rot)
        sx, sy, sz = sc
        cr, sr = self.cr, self.sr
        cv = []
        for vx, vy, vz in mesh.v:
            x, y, z = vx * sx, vy * sy, vz * sz
            rx = R[0][0] * x + R[0][1] * y + R[0][2] * z + px - cx
            ry = R[1][0] * x + R[1][1] * y + R[1][2] * z + py - cy
            rz = R[2][0] * x + R[2][1] * y + R[2][2] * z + pz - cz
            cv.append((rx * cr - ry * sr, rx * sr + ry * cr, rz))
        lit = mesh.lit
        edge = mesh.edge
        tr, tg, tb = tint if tint else (1, 1, 1)
        for idx, col, two, n in mesh.faces:
            pts = [cv[i] for i in idx]
            k = len(pts)
            zc = sum(p[2] for p in pts) / k
            zmin = min(p[2] for p in pts)
            if zc > DRAW or max(p[2] for p in pts) < NEAR:
                continue
            nwx = R[0][0] * n[0] + R[0][1] * n[1] + R[0][2] * n[2]
            nwy = R[1][0] * n[0] + R[1][1] * n[1] + R[1][2] * n[2]
            nwz = R[2][0] * n[0] + R[2][1] * n[1] + R[2][2] * n[2]
            if not two:
                ncx, ncy = nwx * cr - nwy * sr, nwx * sr + nwy * cr
                if ncx * sum(p[0] for p in pts) / k + ncy * sum(p[1] for p in pts) / k + nwz * zc >= 0:
                    continue
            if zmin < NEAR:
                pts = clip_near(pts)
                if len(pts) < 3:
                    continue
            co = []
            for p in pts:
                co.append(CX + p[0] / p[2] * FOC)
                co.append(CY - p[1] / p[2] * FOC)
            if max(co[0::2]) < -40 or min(co[0::2]) > W + 40 or max(co[1::2]) < -40 or min(co[1::2]) > H + 40:
                continue
            if lit:
                lam = nwx * LIGHT[0] + nwy * LIGHT[1] + nwz * LIGHT[2]
                if two:
                    lam = abs(lam)
                inten = 0.28 + 0.72 * (lam if lam > 0 else 0)
            else:
                inten = 1.0
            f = clamp((zc - FOGS) / (DRAW - FOGS), 0, 1)
            g = 1 - f
            fill = hexc(col[0] * tr * inten * g + BG[0] * f, col[1] * tg * inten * g + BG[1] * f,
                        col[2] * tb * inten * g + BG[2] * f)
            if edge:
                out = hexc(edge[0] * tr * g + BG[0] * f, edge[1] * tg * g + BG[1] * f, edge[2] * tb * g + BG[2] * f)
            else:
                out = fill
            self.faces.append((zc + (1000.0 if mesh.bg else 0.0), co, fill, out))

    def flush(self):
        f = self.faces
        f.sort(key=lambda a: -a[0])
        n = min(len(f), POOL)
        c, pool, cache = self.c, self.pool, self.cache
        for i in range(n):
            _, co, fill, out = f[i]
            pid = pool[i]
            c.coords(pid, *co)
            st = (fill, out)
            if cache[i] != st:
                c.itemconfig(pid, fill=fill, outline=out, state='normal')
                cache[i] = st
        for i in range(n, self.shown):
            if cache[i] is not None:
                c.itemconfig(pool[i], state='hidden')
                cache[i] = None
        self.shown = n


# ===================================================================
#  Игра
# ===================================================================
MENU = [('АСТЕРОИДЫ', 'ast'), ('ТОННЕЛЬ', 'tun'), ('КОЛЬЦА', 'ring'), ('ВЫХОД', None)]
LAT = 21.0


class Game:
    def __init__(self, root):
        self.root = root
        self.c = tk.Canvas(root, width=W, height=H, bg='#05050f', highlightthickness=0)
        self.c.pack()
        c = self.c
        for i in range(30):
            k = i / 29
            c.create_rectangle(0, i * H / 30, W, (i + 1) * H / 30 + 1, width=0,
                               fill=hexc(.02 + .05 * k * k, .02 + .02 * k, .07 + .12 * k))
        self.stars = []
        for _ in range(90):
            self.stars.append(O(x=random.uniform(-70, 70), y=random.uniform(-45, 45), z=random.uniform(1, 130),
                                id=c.create_line(0, 0, 0, 0, fill=hexc(*(random.choice([(.9, .9, 1), (.6, .8, 1), (1, .8, .6)])))),
                                ))
        self.scene = Scene(c)
        self.hud = {}
        self.hudtxt = {}
        f = ('Arial', 18, 'bold')
        self.hud['a'] = c.create_text(24, 18, anchor='nw', fill='#ffffff', font=f, text='')
        self.hud['b'] = c.create_text(24, 52, anchor='nw', fill='#7ff', font=('Arial', 15, 'bold'), text='')
        self.hud['t'] = c.create_text(W - 24, 18, anchor='ne', fill='#fd7', font=('Arial', 26, 'bold'), text='')
        self.hud['m'] = c.create_text(CX, 110, fill='#9f9', font=('Arial', 24, 'bold'), text='')
        self.hud['hb'] = c.create_rectangle(W - 224, H - 40, W - 24, H - 22, outline='#fff', fill='#200')
        self.hud['hf'] = c.create_rectangle(W - 224, H - 40, W - 24, H - 22, outline='', fill='#e33')
        self.hud['x'] = [c.create_line(0, 0, 0, 0, fill='#7ff', width=2) for _ in range(4)]
        self.keys, self.pend = set(), {}
        self.mx, self.my, self.mouse_down, self.mouse_steer = CX, CY, False, False
        root.bind('<KeyPress>', self.kdown)
        root.bind('<KeyRelease>', self.kup)
        c.bind('<Motion>', self.on_motion)
        c.bind('<ButtonPress-1>', self.on_click)
        c.bind('<ButtonRelease-1>', lambda e: setattr(self, 'mouse_down', False))
        try:
            with open(SCORE_FILE) as fh:
                HS.update(json.load(fh))
        except (OSError, ValueError):
            pass
        self.sel = 0
        self.state = 'menu'
        self.demo = True
        self.reset('ast')
        self.show_menu()
        self.last = time.perf_counter()
        self.tick()

    # ---------------- ввод
    def kdown(self, e):
        k = e.keysym.lower()
        if k in self.pend:
            self.root.after_cancel(self.pend.pop(k))
        if k not in self.keys:
            self.keys.add(k)
            self.on_key(k)

    def kup(self, e):
        k = e.keysym.lower()

        def rel():
            self.keys.discard(k)
            self.pend.pop(k, None)
        self.pend[k] = self.root.after(30, rel)

    def on_motion(self, e):
        self.mx, self.my = e.x, e.y
        if self.state == 'menu':
            for i in range(len(MENU)):
                if self.btn_y(i) - 28 < e.y < self.btn_y(i) + 28 and abs(e.x - CX) < 230:
                    if self.sel != i:
                        self.sel = i
                        self.paint_menu()

    def on_click(self, e):
        self.mouse_down = True
        if self.state == 'menu':
            for i in range(len(MENU)):
                if self.btn_y(i) - 28 < e.y < self.btn_y(i) + 28 and abs(e.x - CX) < 230:
                    self.choose(i)
        elif self.state == 'over':
            self.show_menu()

    def on_key(self, k):
        if k == 'm':
            self.mouse_steer = not self.mouse_steer
        if self.state == 'menu':
            if k in ('down', 's'):
                self.sel = (self.sel + 1) % len(MENU)
                self.paint_menu()
            elif k in ('up', 'w'):
                self.sel = (self.sel - 1) % len(MENU)
                self.paint_menu()
            elif k in ('return', 'space'):
                self.choose(self.sel)
        elif self.state == 'over':
            if k == 'r':
                self.start(self.mode)
            elif k in ('return', 'escape'):
                self.show_menu()
        elif self.state == 'play' and k == 'escape':
            self.show_menu()

    # ---------------- меню
    def btn_y(self, i):
        return 300 + i * 70

    def show_menu(self):
        self.c.delete('ui')
        self.state = 'menu'
        self.demo = True
        self.reset('ast')
        self.set_hud(False)
        c = self.c
        c.create_text(CX + 3, 143, text='NEON FLIGHT 3D', fill='#000', font=('Arial', 64, 'bold'), tags='ui')
        c.create_text(CX, 140, text='NEON FLIGHT 3D', fill='#5ff', font=('Arial', 64, 'bold'), tags='ui')
        c.create_text(CX, 200, text='python + tkinter, собственный 3D-движок', fill='#bbd', font=('Arial', 15), tags='ui')
        self.mbox, self.mtxt = [], []
        for i, (label, _) in enumerate(MENU):
            y = self.btn_y(i)
            self.mbox.append(c.create_rectangle(CX - 230, y - 28, CX + 230, y + 28, width=3, tags='ui'))
            self.mtxt.append(c.create_text(CX, y, text=label, font=('Arial', 24, 'bold'), tags='ui'))
        c.create_text(CX, H - 62, fill='#fd7', font=('Arial', 15), tags='ui',
                      text='Рекорды:  астероиды %d   |   тоннель %d   |   кольца %d' % (HS['ast'], HS['tun'], HS['ring']))
        c.create_text(CX, H - 32, fill='#99a', font=('Arial', 13), tags='ui',
                      text='WASD / стрелки - лететь | Пробел / ЛКМ - огонь | M - мышь | Esc - меню')
        self.paint_menu()

    def paint_menu(self):
        for i in range(len(MENU)):
            on = i == self.sel
            self.c.itemconfig(self.mbox[i], outline='#5ff' if on else '#446', fill='#124' if on else '#0a0a1c')
            self.c.itemconfig(self.mtxt[i], fill='#fff' if on else '#99a')

    def choose(self, i):
        if MENU[i][1] is None:
            self.root.destroy()
            return
        self.start(MENU[i][1])

    def start(self, mode):
        self.c.delete('ui')
        self.demo = False
        self.state = 'play'
        self.reset(mode)
        self.set_hud(True)

    def set_hud(self, on):
        st = 'normal' if on else 'hidden'
        for k, v in self.hud.items():
            for i in (v if isinstance(v, list) else [v]):
                self.c.itemconfig(i, state=st)
        self.hudtxt.clear()

    def settext(self, key, text):
        if self.hudtxt.get(key) != text:
            self.hudtxt[key] = text
            self.c.itemconfig(self.hud[key], text=text)

    # ---------------- состояние игры
    def reset(self, mode):
        self.mode = mode
        self.px = self.py = self.vx = self.vy = self.pz = 0.0
        self.speed = 30.0 if mode != 'tun' else 28.0
        self.hp, self.score, self.t = 100.0, 0, 0.0
        self.objs, self.bul, self.eb, self.parts = [], [], [], []
        self.cool = self.inv = self.shake = self.spawn = self.dspawn = 0.0
        self.combo = self.rings = 0
        self.dist = 0.0
        self.over, self.newrec = None, False
        self.roll = 0.0
        self.msg_t = 0.0
        self.msg = ''
        self.bonus = 0
        self.XR, self.YR = (16.0, 9.0) if mode != 'tun' else (TL - 1.3, TL - 1.3)
        self.next_gate = 70.0
        self.gap = (1, 1)
        self.nr = (0.0, 0.0, 70.0)
        self.time = 45.0
        self.dspawn = 12.0
        if mode == 'ring':
            self.gen_rings()
        if mode == 'tun':
            self.gen_gates()

    def gen_rings(self):
        while self.nr[2] < self.pz + DRAW:
            x, y, z = self.nr
            self.objs.append(O(kind='ring', x=x, y=y, z=z, passed=False, hit=False, age=0.0))
            self.nr = (clamp(x + random.uniform(-10, 10), -12, 12), clamp(y + random.uniform(-6, 6), -6, 6), z + 38)

    def gen_gates(self):
        while self.next_gate < self.pz + DRAW:
            gx = clamp(self.gap[0] + random.randint(-1, 1), 0, 2)
            gy = clamp(self.gap[1] + random.randint(-1, 1), 0, 2)
            gaps = {(gx, gy), (clamp(gx + random.choice([-1, 1]), 0, 2), gy)}
            self.gap = (gx, gy)
            hue = (self.next_gate * 0.004) % 1
            cell = TL * 2 / 3
            for i in range(3):
                for j in range(3):
                    if (i, j) in gaps:
                        continue
                    self.objs.append(O(kind='blk', x=-TL + cell * (i + .5), y=-TL + cell * (j + .5), z=self.next_gate,
                                       hx=cell / 2 - .06, hy=cell / 2 - .06, hz=1.2, hp=1, hue=hue))
            self.next_gate += max(26.0, self.speed * 0.9)

    def burst(self, x, y, z, col, n=14, spd=7.0):
        for _ in range(n):
            a, b = random.uniform(0, 6.28), random.uniform(-1, 1)
            s = random.uniform(.3, 1) * spd
            self.parts.append(O(x=x, y=y, z=z, vx=math.cos(a) * s, vy=b * s, vz=math.sin(a) * s,
                                life=random.uniform(.35, .8), ml=.8, col=col, sz=random.uniform(.12, .3)))

    # ---------------- обновление
    def update(self, dt):
        self.t += dt
        s = self
        k = self.keys
        if self.demo:
            ax = math.sin(self.t * .6) * 1.0
            ay = math.sin(self.t * .43) * .6
            tx, ty = ax * 7, ay * 4
            ax, ay = clamp((tx - s.px) * 2, -1, 1), clamp((ty - s.py) * 2, -1, 1)
        else:
            ax = ((('right' in k) or ('d' in k)) - (('left' in k) or ('a' in k)))
            ay = ((('up' in k) or ('w' in k)) - (('down' in k) or ('s' in k)))
            if s.mouse_steer:
                ax = clamp(((s.mx / W - .5) * 2 * s.XR * 1.1 - s.px) * .4, -1, 1)
                ay = clamp((-(s.my / H - .5) * 2 * s.YR * 1.1 - s.py) * .4, -1, 1)
        s.vx += (ax * LAT - s.vx) * min(1, dt * 7)
        s.vy += (ay * LAT - s.vy) * min(1, dt * 7)
        s.px = clamp(s.px + s.vx * dt, -s.XR, s.XR)
        s.py = clamp(s.py + s.vy * dt, -s.YR, s.YR)
        if abs(s.px) >= s.XR:
            s.vx = 0
        if abs(s.py) >= s.YR:
            s.vy = 0
        s.roll += (-s.vx * .045 - s.roll) * min(1, dt * 6)
        s.cool -= dt
        s.inv = max(0, s.inv - dt)
        s.shake = max(0, s.shake - dt * 1.5)
        s.msg_t -= dt
        old_pz = s.pz
        s.pz += s.speed * dt
        s.dist += s.speed * dt

        if not s.demo and s.mode != 'ring' and (' ' in k or 'space' in k or s.mouse_down) and s.cool <= 0:
            s.cool = .13
            s.gun = not getattr(s, 'gun', False)
            ox = .6 if s.gun else -.6
            s.bul.append(O(x=s.px + ox, y=s.py - .1, z=s.pz + 1.6, pz=s.pz + 1.6, vz=s.speed + 85, life=1.3))

        getattr(s, 'mode_' + s.mode)(dt, old_pz)

        for b in s.bul:
            b.pz = b.z
            b.z += b.vz * dt
            b.life -= dt
        s.bul = [b for b in s.bul if b.life > 0]
        for b in s.eb:
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.z += b.vz * dt
            b.life -= dt
            if not s.demo and abs(b.z - s.pz) < 2.2 and (b.x - s.px) ** 2 + (b.y - s.py) ** 2 < 1.3:
                b.life = 0
                s.hurt(10)
        s.eb = [b for b in s.eb if b.life > 0]
        for p in s.parts:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.z += p.vz * dt
            p.life -= dt
        s.parts = [p for p in s.parts if p.life > 0]
        s.objs = [o for o in s.objs if o.z > s.pz - 14]
        if not s.demo and s.over is None and s.hp <= 0:
            s.finish('КОРАБЛЬ УНИЧТОЖЕН')

    def hurt(self, d):
        if self.inv > 0 or self.demo:
            return
        self.hp -= d
        self.inv = .9
        self.shake = .6
        self.burst(self.px, self.py, self.pz + 1, (1, .4, .2), 10, 6)

    def finish(self, text):
        if self.over is not None:
            return
        self.over = text
        self.state = 'over'
        sc = int(self.score)
        if sc > HS[self.mode]:
            HS[self.mode] = sc
            self.newrec = True
        try:
            with open(SCORE_FILE, 'w') as fh:
                json.dump(HS, fh)
        except OSError:
            pass
        c = self.c
        c.create_rectangle(0, 0, W, H, fill='#000', stipple='gray50', tags='ui')
        c.create_text(CX, CY - 70, text=text, fill='#ffe', font=('Arial', 40, 'bold'), tags='ui')
        c.create_text(CX, CY - 10, text='Счёт: %d' % sc, fill='#7ff', font=('Arial', 30, 'bold'), tags='ui')
        if self.newrec:
            c.create_text(CX, CY + 40, text='НОВЫЙ РЕКОРД!', fill='#7f7', font=('Arial', 26, 'bold'), tags='ui')
        c.create_text(CX, CY + 100, text='R - ещё раз    Enter - меню', fill='#aab', font=('Arial', 16), tags='ui')

    # ---- общие хелперы для режимов
    def shoot_hits(self, explode):
        for b in self.bul:
            for o in self.objs:
                if o.kind == 'ast' or o.kind == 'drone':
                    if min(b.pz, b.z) - o.r - 1 <= o.z <= max(b.pz, b.z) + o.r + 1 and (o.x - b.x) ** 2 + (o.y - b.y) ** 2 < (o.r + .3) ** 2:
                        b.life = 0
                        o.hp -= 1
                        o.flash = .08
                        if o.hp <= 0:
                            explode(o)
                        break
                elif o.kind == 'blk':
                    if min(b.pz, b.z) - o.hz <= o.z <= max(b.pz, b.z) + o.hz and abs(o.x - b.x) < o.hx + .3 and abs(o.y - b.y) < o.hy + .3:
                        b.life = 0
                        explode(o)
                        break

    # ---------------- режим: астероиды
    def mode_ast(self, dt, old_pz):
        s = self
        s.speed = min(46.0, 30.0 + s.t * .12)
        s.spawn -= dt
        if s.spawn <= 0:
            s.spawn = max(.2, .85 - s.t * .006)
            sz = random.uniform(1.0, 3.0)
            s.objs.append(O(kind='ast', x=s.px + random.uniform(-16, 16), y=s.py + random.uniform(-9, 9),
                            z=s.pz + DRAW - 6, r=sz, hp=int(sz + 1), vx=random.uniform(-1, 1), vy=random.uniform(-1, 1),
                            vz=-random.uniform(0, 6), rot=[random.uniform(0, 6) for _ in range(3)],
                            spin=[random.uniform(-1, 1) for _ in range(3)], mesh=random.choice(AST), flash=0.0))
        if s.t > 14 and not s.demo:
            s.dspawn -= dt
            if s.dspawn <= 0:
                s.dspawn = max(3.0, 9 - s.t * .04)
                s.objs.append(O(kind='drone', x0=random.uniform(-10, 10), y0=random.uniform(-5, 5), x=0, y=0,
                                z=s.pz + DRAW - 15, r=1.6, hp=4, ph=random.uniform(0, 6), ft=random.uniform(1, 2),
                                vz=s.speed * .55, rot=[0, 0, 0], spin=[0, 0, 0], flash=0.0))
        for o in list(s.objs):
            o.flash = max(0, getattr(o, 'flash', 0) - dt)
            if o.kind == 'ast':
                o.x += o.vx * dt
                o.y += o.vy * dt
                o.z += o.vz * dt
                for i in range(3):
                    o.rot[i] += o.spin[i] * dt
                if not s.demo and abs(o.z - s.pz) < o.r + 1.2 and (o.x - s.px) ** 2 + (o.y - s.py) ** 2 < (o.r * .9 + .8) ** 2:
                    s.hurt(14 + o.r * 4)
                    s.destroy_ast(o, False)
            elif o.kind == 'drone':
                o.z += o.vz * dt
                o.x = o.x0 + 5 * math.sin(s.t * 1.3 + o.ph) + (s.px - o.x0) * .4
                o.y = o.y0 + 3 * math.sin(s.t * .9 + o.ph * 2) + (s.py - o.y0) * .3
                o.rot[2] = -math.cos(s.t * 1.3 + o.ph) * .5
                o.ft -= dt
                dz = o.z - s.pz
                if o.ft <= 0 and 20 < dz < 90:
                    o.ft = random.uniform(1.4, 2.4)
                    d = norm((s.px - o.x, s.py - o.y, -dz))
                    s.eb.append(O(x=o.x, y=o.y, z=o.z - 1.5, vx=d[0] * 38, vy=d[1] * 38, vz=d[2] * 38 + s.speed * 0.0, life=4.0))
                if dz < 4:
                    o.hp = 0
                    s.burst(o.x, o.y, o.z, (1, .4, .8), 16)
        s.objs = [o for o in s.objs if not (o.kind == 'drone' and o.hp <= 0)]
        if not s.demo:
            s.shoot_hits(s.explode_ast)
            s.score += dt * 2

    def destroy_ast(self, o, award=True):
        if o in self.objs:
            self.objs.remove(o)
        self.burst(o.x, o.y, o.z, (1, .7, .3), 16, 8)
        if award:
            self.score += int(10 * o.r)
        if o.r > 1.8 and award:
            for sgn in (-1, 1):
                self.objs.append(O(kind='ast', x=o.x + sgn * o.r * .5, y=o.y, z=o.z, r=o.r * .6, hp=int(o.r * .6 + 1),
                                   vx=sgn * 3, vy=random.uniform(-2, 2), vz=o.vz, rot=list(o.rot), spin=list(o.spin),
                                   mesh=o.mesh, flash=0.0))

    def explode_ast(self, o):
        if o.kind == 'ast':
            self.destroy_ast(o)
        elif o.kind == 'drone':
            self.objs.remove(o)
            self.burst(o.x, o.y, o.z, (1, .4, .9), 26, 10)
            self.score += 50
        else:
            self.explode_blk(o)

    # ---------------- режим: тоннель
    def mode_tun(self, dt, old_pz):
        s = self
        s.speed = min(62.0, 28.0 + s.t * .55)
        s.gen_gates()
        s.score = s.dist / 10 + getattr(s, 'bonus', 0)
        for o in s.objs:
            if abs(o.z - s.pz) < o.hz + .9 and abs(o.x - s.px) < o.hx + .7 and abs(o.y - s.py) < o.hy + .5:
                s.hurt(30)
                s.explode_blk(o, False)
        s.objs = [o for o in s.objs if o.hp > 0]
        s.shoot_hits(s.explode_blk)

    def explode_blk(self, o, award=True):
        o.hp = 0
        hx = hexc(*hsv(o.hue, .8, 1))
        self.burst(o.x, o.y, o.z, hsv(o.hue, .7, 1), 14, 9)
        if award:
            self.bonus = getattr(self, 'bonus', 0) + 5

    # ---------------- режим: кольца
    def mode_ring(self, dt, old_pz):
        s = self
        s.speed = 30 + min(26, s.rings * .9)
        s.time -= dt
        s.gen_rings()
        for o in s.objs:
            o.age += dt
            if not o.passed and o.z <= s.pz:
                o.passed = True
                if math.hypot(s.px - o.x, s.py - o.y) < 3.4:
                    o.hit = True
                    s.rings += 1
                    s.combo += 1
                    s.score += 10 * s.combo
                    s.time = min(99, s.time + 3)
                    s.burst(o.x, o.y, o.z, (.4, 1, .5), 30, 12)
                    s.msg = 'КОМБО x%d' % s.combo if s.combo > 1 else 'КОЛЬЦО!'
                    s.msg_t = 1.0
                else:
                    s.combo = 0
                    s.msg = 'ПРОМАХ'
                    s.msg_t = 1.0
        if s.time <= 0:
            s.finish('ВРЕМЯ ВЫШЛО!  Колец: %d' % s.rings)

    # ---------------- отрисовка
    def draw(self):
        s = self
        sh = s.shake
        cam = (s.px * .65 + random.uniform(-sh, sh), s.py * .65 + 1.8 + random.uniform(-sh, sh), s.pz - 10.0)
        sc = s.scene
        sc.begin(cam, s.roll * .5)
        # звёзды
        spd = s.speed
        cr, sr = sc.cr, sc.sr
        for st in s.stars:
            z = (st.z - cam[2]) % 130.0 + 1.0
            x, y = st.x - cam[0] * .5, st.y - cam[1] * .5
            x1, y1 = x * cr - y * sr, x * sr + y * cr
            z2 = z + spd * .035
            s.c.coords(st.id, CX + x1 / z * FOC, CY - y1 / z * FOC, CX + x1 / z2 * FOC, CY - y1 / z2 * FOC)
        # тоннель
        if s.mode == 'tun':
            sl = 6.0
            k0 = int((cam[2]) // sl)
            for i in range(k0, k0 + int(DRAW / sl) + 2):
                hue = (i * .035) % 1
                t = hsv(hue, .85, 1)
                sc.add(TUNNEL, (0, 0, i * sl), tint=(t[0], t[1], t[2]))
        # объекты
        for o in s.objs:
            k = o.kind
            if k == 'ast':
                tint = (2.2, 2.2, 2.2) if o.flash > 0 else None
                sc.add(o.mesh, (o.x, o.y, o.z), tuple(o.rot), (o.r, o.r, o.r), tint)
            elif k == 'drone':
                tint = (2.2, 2.2, 2.2) if o.flash > 0 else None
                sc.add(DRONE, (o.x, o.y, o.z), (0, math.pi, o.rot[2]), (1, 1, 1), tint)
            elif k == 'blk':
                t = hsv(o.hue, .8, 1)
                sc.add(BOX[0], (o.x, o.y, o.z), (0, 0, 0), (o.hx, o.hy, o.hz), (t[0], t[1], t[2]))
            elif k == 'ring':
                if o.passed:
                    col = (.3, 1, .4) if o.hit else (1, .25, .25)
                else:
                    first = min((q.z for q in s.objs if q.kind == 'ring' and not q.passed), default=0)
                    col = (1, .85, .2) if o.z == first else (.3, .8, 1)
                sc.add(RING, (o.x, o.y, o.z), (0, 0, o.age * .8), (1, 1, 1), col)
        for b in s.bul:
            sc.add(BOLT_P, (b.x, b.y, b.z))
        for b in s.eb:
            sc.add(BOLT_E, (b.x, b.y, b.z), (0, 0, 0), (1.4, 1.4, 1.4))
        for p in s.parts:
            f = p.life / p.ml
            sz = p.sz * (.3 + f)
            sc.add(SPARK, (p.x, p.y, p.z), (0, 0, p.life * 8), (sz, sz, sz), (p.col[0] * f + .15, p.col[1] * f + .1, p.col[2] * f + .1))
        if s.hp > 0 and not (s.inv > 0 and int(s.t * 20) % 2):
            sc.add(SHIP, (s.px, s.py, s.pz), (-s.vy * .02, 0, s.roll * 3), (1, 1, 1))
            fl = .8 + .5 * random.random()
            sc.add(FLAME, (s.px, s.py, s.pz), (-s.vy * .02, 0, s.roll * 3), (1, 1, fl))
        sc.flush()

        # прицел и интерфейс
        if s.state == 'play':
            if s.mode != 'ring':
                z = s.pz + 45 - cam[2]
                x, y = s.px - cam[0], s.py - cam[1]
                x1, y1 = x * cr - y * sr, x * sr + y * cr
                cx, cy = CX + x1 / z * FOC, CY - y1 / z * FOC
                for i, (a, b, c2, d) in enumerate([(-14, 0, -5, 0), (5, 0, 14, 0), (0, -14, 0, -5), (0, 5, 0, 14)]):
                    s.c.coords(s.hud['x'][i], cx + a, cy + b, cx + c2, cy + d)
            else:
                for i in s.hud['x']:
                    s.c.coords(i, 0, 0, 0, 0)
            s.c.coords(s.hud['hf'], W - 224, H - 40, W - 224 + 200 * clamp(s.hp, 0, 100) / 100, H - 22)
            if s.mode == 'ast':
                s.settext('a', 'СЧЁТ %d' % s.score)
                s.settext('b', 'Скорость %d' % s.speed)
                s.settext('t', '')
            elif s.mode == 'tun':
                s.settext('a', 'ДИСТАНЦИЯ %d' % s.score)
                s.settext('b', 'Скорость %d' % s.speed)
                s.settext('t', '')
            else:
                s.settext('a', 'СЧЁТ %d' % s.score)
                s.settext('b', 'Колец: %d   Комбо: x%d' % (s.rings, s.combo))
                s.settext('t', '%.1f' % max(0, s.time))
            s.settext('m', getattr(s, 'msg', '') if s.msg_t > 0 else '')

    def tick(self):
        now = time.perf_counter()
        dt = min(now - self.last, .05)
        self.last = now
        if self.state != 'over':
            self.update(dt)
        else:
            self.t += dt
            self.pz += self.speed * dt * .2
        self.draw()
        self.root.after(8, self.tick)


def main():
    root = tk.Tk()
    root.title('NEON FLIGHT 3D')
    root.resizable(False, False)
    Game(root)
    root.mainloop()


if __name__ == '__main__':
    main()
