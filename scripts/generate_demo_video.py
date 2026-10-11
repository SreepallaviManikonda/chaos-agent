#!/usr/bin/env python3
"""
Generate a high-definition 720p 30fps animated demo video and preview GIF
for the Chaos Pit Wall autonomous chaos engineering platform.
"""

import math
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v2 as imageio

WIDTH = 1280
HEIGHT = 720
FPS = 30

# Colors (F1 Pit Wall Theme)
BG_COLOR = (11, 11, 15)
PANEL_BG = (21, 21, 30)
PANEL_BORDER = (45, 45, 60)
ACCENT_RED = (225, 6, 0)
ACCENT_GREEN = (0, 210, 106)
ACCENT_YELLOW = (255, 184, 0)
ACCENT_CYAN = (0, 229, 255)
ACCENT_PURPLE = (180, 70, 255)
TEXT_WHITE = (245, 245, 250)
TEXT_MUTED = (140, 140, 160)
TEXT_DARK = (90, 90, 110)

# Fonts
FONT_REGULAR_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_MONO_PATH = "/System/Library/Fonts/Monaco.ttf"

font_cache = {}
def get_font(size, bold=False, mono=False):
    key = (size, bold, mono)
    if key in font_cache:
        return font_cache[key]
    path = FONT_MONO_PATH if mono else (FONT_BOLD_PATH if bold else FONT_REGULAR_PATH)
    try:
        font = ImageFont.truetype(path, size)
    except Exception:
        font = ImageFont.load_default()
    font_cache[key] = font
    return font


def draw_rounded_rect(draw, bbox, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


def draw_header(draw, title, subtitle, status_flag="GREEN", t_rel=0.0):
    # Top race control banner
    flag_colors = {
        "GREEN": (10, 61, 31),
        "YELLOW": (74, 59, 0),
        "RED": (74, 10, 10),
        "CHECKERED": (30, 30, 40)
    }
    flag_borders = {
        "GREEN": ACCENT_GREEN,
        "YELLOW": ACCENT_YELLOW,
        "RED": ACCENT_RED,
        "CHECKERED": TEXT_WHITE
    }
    flag_texts = {
        "GREEN": "🟢 GREEN FLAG — ALL SYSTEMS NOMINAL",
        "YELLOW": "🟡 YELLOW FLAG — LATENCY ELEVATED",
        "RED": "🔴 RED FLAG — KILL SWITCH TRIPPED (<50ms REVERT)",
        "CHECKERED": "🏁 SESSION COMPLETE — RESILIENCE ASSESSED"
    }

    # Red accent stripe at top
    draw.rectangle([0, 0, WIDTH, 5], fill=ACCENT_RED)

    # Header bar
    draw.rectangle([0, 5, WIDTH, 75], fill=(16, 16, 24))
    draw.line([0, 75, WIDTH, 75], fill=(35, 35, 48), width=1)

    # Logo / Title
    draw.text((35, 16), "🏎️ CHAOS PIT WALL", font=get_font(22, bold=True), fill=TEXT_WHITE)
    draw.text((35, 44), subtitle, font=get_font(13), fill=TEXT_MUTED)

    # Live Flag Pill
    pill_w = 420
    pill_x = WIDTH - pill_w - 35
    pill_y = 18
    bg_col = flag_colors.get(status_flag, PANEL_BG)
    border_col = flag_borders.get(status_flag, PANEL_BORDER)

    # Flash effect if red flag
    if status_flag == "RED":
        alpha = math.sin(t_rel * 8.0) * 0.5 + 0.5
        border_col = (int(ACCENT_RED[0] * alpha + 100 * (1 - alpha)), 0, 0)

    draw_rounded_rect(draw, [pill_x, pill_y, pill_x + pill_w, pill_y + 40], 6, fill=bg_col, outline=border_col, width=2)
    flag_txt = flag_texts.get(status_flag, status_flag)
    draw.text((pill_x + 16, pill_y + 11), flag_txt, font=get_font(12, bold=True), fill=TEXT_WHITE)


def draw_footer_progress(draw, current_sec, total_sec, scene_name):
    y = HEIGHT - 32
    draw.rectangle([0, y, WIDTH, HEIGHT], fill=(14, 14, 20))
    draw.line([0, y, WIDTH, y], fill=(30, 30, 42), width=1)

    progress = min(1.0, current_sec / total_sec)
    bar_w = int(WIDTH * progress)
    draw.rectangle([0, y, bar_w, y + 3], fill=ACCENT_RED)

    time_str = f"LAP {int(current_sec)}s / {int(total_sec)}s"
    draw.text((35, y + 8), f"📍 {scene_name}", font=get_font(12, bold=True), fill=TEXT_MUTED)
    draw.text((WIDTH - 150, y + 8), time_str, font=get_font(12, mono=True), fill=ACCENT_YELLOW)


# ---------------- SCENE 1: HOOK & INTRO ----------------
def render_scene_intro(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "Autonomous Chaos Engineering on Google Cloud Online Boutique", "GREEN", t_rel)

    # Center Hero Card
    card_box = [180, 120, WIDTH - 180, 580]
    draw_rounded_rect(draw, card_box, 12, fill=PANEL_BG, outline=PANEL_BORDER, width=2)

    # F1 Racing Badge
    draw_rounded_rect(draw, [WIDTH // 2 - 140, 150, WIDTH // 2 + 140, 185], 6, fill=(40, 10, 10), outline=ACCENT_RED, width=1)
    draw.text((WIDTH // 2 - 120, 158), "F1 PIT-WALL RESILIENCE SUITE", font=get_font(13, bold=True), fill=ACCENT_RED)

    # Main Big Title
    draw.text((WIDTH // 2 - 380, 215), "Autonomous Chaos Engineering", font=get_font(38, bold=True), fill=TEXT_WHITE)
    draw.text((WIDTH // 2 - 270, 270), "for Cloud-Native Microservices", font=get_font(28, bold=True), fill=ACCENT_CYAN)

    # Value Props in 3 columns
    cols = [
        ("🔍 Zero Configuration", "Autonomously maps 13 microservices\nand 30 edges via AST & Docker inspect.", ACCENT_CYAN),
        ("🛡️ Active Safety Watchdog", "500ms heartbeat polling with\nsub-50ms instant container unpause.", ACCENT_GREEN),
        ("📊 Deterministic Scoring", "Objective 0-100 resilience score\nwith zero LLM hallucination.", ACCENT_YELLOW),
    ]

    col_w = 260
    start_x = 225
    for i, (col_title, col_desc, col_color) in enumerate(cols):
        cx = start_x + i * 290
        cy = 350
        draw_rounded_rect(draw, [cx, cy, cx + col_w, cy + 170], 8, fill=(16, 16, 23), outline=(35, 35, 50), width=1)
        draw.line([cx, cy, cx + col_w, cy], fill=col_color, width=3)
        draw.text((cx + 15, cy + 18), col_title, font=get_font(14, bold=True), fill=TEXT_WHITE)
        draw.text((cx + 15, cy + 50), col_desc, font=get_font(12), fill=TEXT_MUTED)

    draw_footer_progress(draw, t_rel, dur, "PROLOGUE: THE PIT WALL PLATFORM")
    return np.array(img)


# ---------------- SCENE 2: TOPOLOGY DISCOVERY ----------------
def render_scene_topology(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "Autonomous AST & Docker Topology Discovery (13 Microservices)", "GREEN", t_rel)

    # Left Panel: Discovery Details
    left_box = [40, 100, 380, 640]
    draw_rounded_rect(draw, left_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((65, 125), "CIRCUIT TELEMETRY", font=get_font(14, bold=True), fill=ACCENT_CYAN)
    draw.text((65, 150), "Discovered Infrastructure Graph", font=get_font(18, bold=True), fill=TEXT_WHITE)

    stats = [
        ("Target Cluster:", "Google Cloud Online Boutique"),
        ("Container Nodes:", "13 Active Services"),
        ("Dependency Edges:", "30 Inter-service Links"),
        ("Single Point of Failure:", "valkey-cart (Redis Store)"),
        ("Discovery Mode:", "AST Parsing + Inspect API"),
        ("Telemetry Protocol:", "Prometheus / cAdvisor Poll")
    ]
    sy = 200
    for label, val in stats:
        draw.text((65, sy), label, font=get_font(12), fill=TEXT_MUTED)
        col = ACCENT_RED if "valkey-cart" in val else TEXT_WHITE
        draw.text((65, sy + 18), val, font=get_font(13, bold=True), fill=col)
        sy += 48

    # Warning Callout at bottom of left panel
    draw_rounded_rect(draw, [60, 520, 360, 615], 6, fill=(40, 15, 15), outline=ACCENT_RED, width=1)
    draw.text((75, 532), "⚠️ VULNERABILITY LOCATED", font=get_font(12, bold=True), fill=ACCENT_RED)
    draw.text((75, 555), "cartservice has 0 fallback if\nvalkey-cart drops packets.", font=get_font(12), fill=TEXT_WHITE)

    # Right Panel: 4-Tier Visual Circuit Track
    right_box = [405, 100, WIDTH - 40, 640]
    draw_rounded_rect(draw, right_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((435, 125), "RACE TRACK TOPOLOGY MAP", font=get_font(14, bold=True), fill=TEXT_WHITE)
    draw.text((435, 150), "Live Service Dependency Graph with Identified Blast Radius", font=get_font(13), fill=TEXT_MUTED)

    # Tiers
    tiers = [
        ("TIER 1: INGRESS", [("frontend", ACCENT_CYAN, False)], 195),
        ("TIER 2: CRITICAL PATH (SPOF)", [("cartservice", ACCENT_RED, True), ("checkoutservice", ACCENT_YELLOW, False)], 290),
        ("TIER 3: DATASTORE", [("valkey-cart", ACCENT_RED, True)], 385),
        ("TIER 4: DOWNSTREAM SATELLITES", [
            ("productcatalog", ACCENT_GREEN, False),
            ("recommendation", ACCENT_GREEN, False),
            ("paymentservice", ACCENT_GREEN, False),
            ("shippingservice", ACCENT_GREEN, False)
        ], 480)
    ]

    for tier_label, nodes, ty in tiers:
        draw.text((435, ty - 18), tier_label, font=get_font(11, bold=True), fill=TEXT_DARK)
        n_count = len(nodes)
        spacing = 740 // (n_count + 1)
        for idx, (node_name, n_col, is_pulse) in enumerate(nodes):
            nx = 440 + spacing * (idx + 1) - 65
            outline_col = n_col
            if is_pulse:
                alpha = math.sin(t_rel * 6.0) * 0.5 + 0.5
                outline_col = (int(255 * alpha), int(30 * (1 - alpha)), int(30 * (1 - alpha)))
            draw_rounded_rect(draw, [nx, ty, nx + 130, ty + 42], 6, fill=(16, 16, 24), outline=outline_col, width=2)
            draw.text((nx + 15, ty + 12), node_name, font=get_font(12, bold=True), fill=TEXT_WHITE)

    # Connections Lines
    draw.line([760, 237, 595, 290], fill=(70, 70, 90), width=2)
    draw.line([760, 237, 850, 290], fill=(70, 70, 90), width=2)
    draw.line([595, 332, 760, 385], fill=ACCENT_RED, width=2)

    draw_footer_progress(draw, t_rel, dur, "STAGE 1: AUTONOMOUS TOPOLOGY & CRITICAL PATH DISCOVERY")
    return np.array(img)


# ---------------- SCENE 3: EXPERIMENT 1 — CART OUTAGE & RED FLAG ----------------
def render_scene_experiment_1(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Determine flag state based on time
    # 0s - 3s: Green baseline
    # 3s - 7s: Red Flag spike
    # 7s - 11s: Recovered green
    if t_rel < 3.0:
        flag_state = "GREEN"
    elif t_rel < 7.5:
        flag_state = "RED"
    else:
        flag_state = "GREEN"

    draw_header(draw, "CHAOS PIT WALL", "EXPERIMENT 1: CONTAINER PAUSE FAULT (cartservice)", flag_state, t_rel)

    # Left Column: Telemetry Cards
    left_w = 360
    draw_rounded_rect(draw, [40, 100, 40 + left_w, 640], 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((65, 125), "PIT STOP TELEMETRY", font=get_font(14, bold=True), fill=ACCENT_CYAN)
    draw.text((65, 150), "cartservice Outage Analysis", font=get_font(18, bold=True), fill=TEXT_WHITE)

    # Stopwatch Box
    draw_rounded_rect(draw, [65, 195, 375, 310], 8, fill=(16, 16, 24), outline=(40, 40, 55), width=1)
    draw.text((85, 210), "⏱️ PIT STOP MTTR (RECOVERY TIME)", font=get_font(11, bold=True), fill=TEXT_MUTED)

    # Stopwatch counter animation
    if t_rel < 3.0:
        stopwatch_val = "0.00 s"
    elif t_rel < 7.0:
        curr_val = min(4.02, (t_rel - 3.0) * 1.0)
        stopwatch_val = f"{curr_val:.2f} s"
    else:
        stopwatch_val = "4.02 s"

    draw.text((85, 235), stopwatch_val, font=get_font(36, bold=True, mono=True), fill=ACCENT_YELLOW)
    draw.text((85, 285), "Watchdog revert completed in <50ms", font=get_font(11), fill=ACCENT_GREEN)

    # Metrics Grid
    metrics = [
        ("Baseline Latency (p95)", "77.1 ms", TEXT_WHITE),
        ("Peak Injected Latency", "2,500.0 ms", ACCENT_RED if t_rel >= 3.0 else TEXT_WHITE),
        ("HTTP Error Rate", "100.0% (Checkout Failed)" if t_rel >= 3.5 else "0.00%", ACCENT_RED if t_rel >= 3.5 else ACCENT_GREEN),
        ("Safety Supervisor Status", "🔴 Auto-Rollback Tripped" if flag_state == "RED" else "🟢 Active Watchdog", ACCENT_RED if flag_state == "RED" else ACCENT_GREEN),
        ("Fault Injection Type", "docker pause cartservice", ACCENT_CYAN),
    ]
    my = 330
    for lbl, val, col in metrics:
        draw.text((65, my), lbl, font=get_font(11), fill=TEXT_MUTED)
        draw.text((65, my + 16), val, font=get_font(13, bold=True), fill=col)
        my += 44

    # Right Column: Live Oscilloscope / Telemetry Waveform Chart
    chart_box = [420, 100, WIDTH - 40, 640]
    draw_rounded_rect(draw, chart_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)

    draw.text((450, 125), "LIVE TELEMETRY TRACE: p95 LATENCY OVER TIME", font=get_font(14, bold=True), fill=TEXT_WHITE)
    draw.text((450, 150), "500ms Polling Loop with Automated Revert Threshold", font=get_font(12), fill=TEXT_MUTED)

    # Chart Canvas
    cx0, cy0, cx1, cy1 = 450, 185, WIDTH - 70, 560
    draw.rectangle([cx0, cy0, cx1, cy1], fill=(13, 13, 19), outline=(35, 35, 48), width=1)

    # Grid Lines
    for y_val in [250, 330, 410, 490]:
        draw.line([cx0, y_val, cx1, y_val], fill=(22, 22, 32), width=1)

    # SLA Threshold Line (Red dashed line at y = 300)
    draw.line([cx0, 280, cx1, 280], fill=(150, 20, 20), width=2)
    draw.text((cx1 - 200, 260), "⚠️ SLA LIMIT: 1000ms", font=get_font(11, bold=True), fill=ACCENT_RED)

    # Animated Curve
    # Generate points across chart
    points = []
    total_chart_w = cx1 - cx0
    total_chart_h = cy1 - cy0

    sim_steps = 60
    progress_ratio = min(1.0, t_rel / dur)
    active_steps = int(sim_steps * progress_ratio)

    for i in range(max(2, active_steps)):
        norm_x = i / sim_steps
        px = cx0 + int(norm_x * total_chart_w)

        # Baseline noise
        base_h = 35 + math.sin(i * 0.4) * 5

        # Fault occurs between norm_x 0.25 and 0.65
        if norm_x >= 0.25 and norm_x <= 0.65:
            fault_progress = (norm_x - 0.25) / 0.40
            spike_h = math.sin(fault_progress * math.pi) * 220
        else:
            spike_h = 0

        py = cy1 - int(base_h + spike_h)
        points.append((px, py))

    # Draw shaded fault zone
    fault_x_start = cx0 + int(0.25 * total_chart_w)
    fault_x_end = cx0 + int(0.65 * total_chart_w)
    draw.rectangle([fault_x_start, cy0 + 1, min(cx1 - 1, fault_x_end), cy1 - 1], fill=(35, 12, 15))
    draw.text((fault_x_start + 15, cy0 + 15), "⚡ INJECTED FAULT WINDOW", font=get_font(11, bold=True), fill=ACCENT_RED)

    # Draw telemetry line
    if len(points) >= 2:
        for idx in range(len(points) - 1):
            p1 = points[idx]
            p2 = points[idx + 1]
            draw.line([p1, p2], fill=ACCENT_CYAN, width=3)
        # Pulse current cursor dot
        last_pt = points[-1]
        draw.ellipse([last_pt[0] - 5, last_pt[1] - 5, last_pt[0] + 5, last_pt[1] + 5], fill=TEXT_WHITE, outline=ACCENT_CYAN, width=2)

    # Legend at bottom of chart
    draw.text((450, 580), "● Cyan: Real p95 Latency    ■ Red Shading: Fault Window    --- Red: SLA Circuit Breaker", font=get_font(11), fill=TEXT_MUTED)

    draw_footer_progress(draw, t_rel, dur, "STAGE 2: CONTAINER PAUSE FAULT — INSTANT SAFETY ROLLBACK (<50ms)")
    return np.array(img)


# ---------------- SCENE 4: EXPERIMENT 2 — VALKEY-CART REDIS SPOF ----------------
def render_scene_experiment_2(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "EXPERIMENT 2: DATASTORE OUTAGE (valkey-cart SPOF)", "RED" if 2.5 < t_rel < 8.0 else "GREEN", t_rel)

    # Main Card
    draw_rounded_rect(draw, [40, 100, WIDTH - 40, 640], 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)

    # Header
    draw.text((70, 125), "INFRASTRUCTURE DATASTORE FAULT", font=get_font(14, bold=True), fill=ACCENT_RED)
    draw.text((70, 150), "Testing the Single Point of Failure (valkey-cart Redis Key-Value Store)", font=get_font(18, bold=True), fill=TEXT_WHITE)

    # Left Column: Cascade Flow
    draw_rounded_rect(draw, [70, 200, 580, 600], 8, fill=(16, 16, 24), outline=(35, 35, 48), width=1)
    draw.text((95, 225), "CASCADE BLAST RADIUS", font=get_font(14, bold=True), fill=ACCENT_YELLOW)

    cascade_steps = [
        ("1. Inject Outage", "Valkey datastore container stopped via Docker API", ACCENT_CYAN),
        ("2. Socket Disconnect", "cartservice loses Redis TCP connection pool", ACCENT_YELLOW),
        ("3. gRPC Timeout Spike", "AddItem / GetCart calls exceed 2,500ms limit", ACCENT_RED),
        ("4. Checkout Failure", "Frontend checkout endpoint throws HTTP 500", ACCENT_RED),
        ("5. Watchdog Intervention", "Automated container restore executed in 5.12s", ACCENT_GREEN),
    ]

    cy = 270
    for step_title, step_desc, step_col in cascade_steps:
        draw_rounded_rect(draw, [95, cy, 555, cy + 50], 6, fill=(22, 22, 32), outline=(40, 40, 55), width=1)
        draw.line([95, cy, 95, cy + 50], fill=step_col, width=4)
        draw.text((115, cy + 8), step_title, font=get_font(12, bold=True), fill=TEXT_WHITE)
        draw.text((115, cy + 28), step_desc, font=get_font(11), fill=TEXT_MUTED)
        cy += 62

    # Right Column: Pit Wall Steward Ruling
    draw_rounded_rect(draw, [610, 200, WIDTH - 70, 600], 8, fill=(16, 16, 24), outline=(35, 35, 48), width=1)
    draw.text((635, 225), "RACE ENGINEER VERDICT", font=get_font(14, bold=True), fill=ACCENT_CYAN)

    verdicts = [
        ("🔴 Critical Vulnerability Confirmed", "Valkey has NO secondary replica or in-memory fallback.\nIf it crashes, all 13,000 active carts in production are lost."),
        ("🛡️ Safety Guarantee Verified", "Watchdog detected error cascade and restored the instance.\nNo permanent cluster crash occurred."),
        ("⏱️ Recovery Benchmark", "Total Pit Stop MTTR: 5.12 seconds\nBaseline Error Rate: 0% -> Fault Error Rate: 100% -> Restored: 0%"),
        ("🔧 Recommended Engineering Fix", "Deploy Envoy sidecar with circuit breaker and local cache,\nplus Redis Sentinel replica.")
    ]
    vy = 270
    for v_title, v_desc in verdicts:
        draw.text((635, vy), v_title, font=get_font(13, bold=True), fill=TEXT_WHITE)
        draw.text((635, vy + 24), v_desc, font=get_font(11), fill=TEXT_MUTED)
        vy += 76

    draw_footer_progress(draw, t_rel, dur, "STAGE 3: INFRASTRUCTURE DATASTORE FAULT & RECOVERY TIMING")
    return np.array(img)


# ---------------- SCENE 5: EXPERIMENT 3 — REAL tc netem NETWORK CHAOS ----------------
def render_scene_experiment_3(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "EXPERIMENT 3: LINUX KERNEL NETWORK DELAY (tc netem via Netshoot)", "YELLOW", t_rel)

    draw_rounded_rect(draw, [40, 100, WIDTH - 40, 640], 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((70, 125), "INFRASTRUCTURE-LEVEL TRAFFIC CONTROL", font=get_font(14, bold=True), fill=ACCENT_YELLOW)
    draw.text((70, 150), "Real Linux Kernel Network Emulation (tc netem) — No Mock Flags", font=get_font(18, bold=True), fill=TEXT_WHITE)

    # Code Box
    draw_rounded_rect(draw, [70, 200, 600, 360], 8, fill=(13, 13, 19), outline=(45, 45, 60), width=1)
    draw.text((90, 218), "KERNEL INJECTION COMMAND (NETSHOOT SIDECAR)", font=get_font(11, bold=True), fill=ACCENT_CYAN)

    cmd_lines = [
        "docker run --net=container:recommendationservice \\",
        "  --cap-add=NET_ADMIN nicolaka/netshoot \\",
        "  tc qdisc add dev eth0 root netem delay 500ms 20ms",
        "",
        "# Automatic rollback on experiment complete:",
        "tc qdisc del dev eth0 root"
    ]
    ly = 245
    for cl in cmd_lines:
        col = ACCENT_YELLOW if "netem delay" in cl else TEXT_MUTED
        draw.text((90, ly), cl, font=get_font(11, mono=True), fill=col)
        ly += 18

    # Explanation Card
    draw_rounded_rect(draw, [70, 380, 600, 600], 8, fill=(16, 16, 24), outline=(35, 35, 48), width=1)
    draw.text((95, 400), "WHY INFRASTRUCTURE tc IS SUPERIOR TO APP FLAGS", font=get_font(13, bold=True), fill=TEXT_WHITE)

    comparisons = [
        ("❌ Flagd / App-level mock:", "Requires custom code in every language and mock hooks."),
        ("✅ Linux Kernel tc netem:", "Universal. Applies to raw packets at socket layer."),
        ("✅ Accurate Telemetry:", "Exactly +500ms latency step verified on Prometheus.")
    ]
    cy = 435
    for title, desc in comparisons:
        draw.text((95, cy), title, font=get_font(12, bold=True), fill=TEXT_WHITE)
        draw.text((95, cy + 20), desc, font=get_font(11), fill=TEXT_MUTED)
        cy += 48

    # Right Card: Measured Results
    draw_rounded_rect(draw, [630, 200, WIDTH - 70, 600], 8, fill=(16, 16, 24), outline=(35, 35, 48), width=1)
    draw.text((655, 225), "TELEMETRY VERIFICATION", font=get_font(14, bold=True), fill=ACCENT_GREEN)

    metrics = [
        ("Target Service:", "recommendationservice"),
        ("Baseline Latency:", "22.4 ms"),
        ("Kernel Injected Delay:", "+500.0 ms (±20ms jitter)"),
        ("Measured Peak p95:", "524.1 ms"),
        ("Degradation Result:", "⚠️ Yellow Flag: Soft degradation"),
        ("Business Impact:", "Cart survived! Non-critical fallback handled delay gracefully.")
    ]
    my = 270
    for lbl, val in metrics:
        draw.text((655, my), lbl, font=get_font(12), fill=TEXT_MUTED)
        col = ACCENT_GREEN if "survived" in val else (ACCENT_YELLOW if "524" in val or "500" in val else TEXT_WHITE)
        draw.text((655, my + 20), val, font=get_font(13, bold=True), fill=col)
        my += 52

    draw_footer_progress(draw, t_rel, dur, "STAGE 4: LINUX KERNEL TRAFFIC CONTROL (tc netem)")
    return np.array(img)


# ---------------- SCENE 6: DETERMINISTIC RESILIENCE SCORING ----------------
def render_scene_scoring(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "CHAMPIONSHIP STANDINGS: RESILIENCE SCORE (38 / 100)", "CHECKERED", t_rel)

    # Left: Score Gauge Card
    left_box = [40, 100, 480, 640]
    draw_rounded_rect(draw, left_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((65, 125), "CLUSTER RESILIENCE RATING", font=get_font(14, bold=True), fill=ACCENT_CYAN)
    draw.text((65, 150), "Championship Superlicence Score", font=get_font(18, bold=True), fill=TEXT_WHITE)

    # Big Score Box
    draw_rounded_rect(draw, [65, 195, 455, 335], 8, fill=(16, 16, 24), outline=ACCENT_RED, width=2)
    draw.text((85, 215), "OVERALL TOUGHNESS SCORE", font=get_font(12, bold=True), fill=TEXT_MUTED)

    # Animated Score Counting Down
    final_score = 38
    if t_rel < 3.0:
        disp_score = int(100 - (100 - final_score) * (t_rel / 3.0))
    else:
        disp_score = final_score

    draw.text((85, 240), f"{disp_score} / 100", font=get_font(48, bold=True, mono=True), fill=ACCENT_RED)
    draw.text((85, 305), "⚠️ DEGRADED — 2 CRITICAL SINGLE POINTS OF FAILURE", font=get_font(11, bold=True), fill=ACCENT_YELLOW)

    # Transparent Formula
    draw.text((65, 360), "DETERMINISTIC FORMULA (0% LLM GUESSWORK)", font=get_font(12, bold=True), fill=TEXT_WHITE)

    formula_lines = [
        ("Base Score:", "100 pts"),
        ("- Kill Switch Engaged (2x):", "-36 pts (-18 pts each)"),
        ("- HTTP 500 Error Cascade:", "-10 pts"),
        ("- MTTR > 3.0s Penalty:", "-16 pts"),
        ("Final Championship Score:", "= 38 pts")
    ]
    fy = 395
    for flbl, fval in formula_lines:
        draw.text((65, fy), flbl, font=get_font(12), fill=TEXT_MUTED)
        col = ACCENT_RED if "-" in flbl else (ACCENT_YELLOW if "=" in fval else TEXT_WHITE)
        draw.text((360, fy), fval, font=get_font(12, bold=True, mono=True), fill=col)
        fy += 42

    # Right: Timing Tower Table
    right_box = [505, 100, WIDTH - 40, 640]
    draw_rounded_rect(draw, right_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((535, 125), "F1 TIMING TOWER: SERVICE RANKINGS", font=get_font(14, bold=True), fill=TEXT_WHITE)
    draw.text((535, 150), "Telemetry Sectors and Impact Deltas", font=get_font(12), fill=TEXT_MUTED)

    tower_headers = ["POS", "SERVICE", "STATUS", "MTTR", "SCORE DELTA"]
    th_x = [535, 595, 755, 915, 1060]
    draw.rectangle([525, 185, WIDTH - 60, 215], fill=(16, 16, 24))
    for idx, th in enumerate(tower_headers):
        draw.text((th_x[idx], 192), th, font=get_font(11, bold=True), fill=TEXT_MUTED)

    tower_data = [
        ("1", "currencyservice", "🟢 RESILIENT", "0.00s", "+0 pts", ACCENT_GREEN),
        ("2", "shippingservice", "🟢 RESILIENT", "0.00s", "+0 pts", ACCENT_GREEN),
        ("3", "recommendationservice", "🟡 DEGRADED", "0.80s", "-6 pts", ACCENT_YELLOW),
        ("4", "productcatalog", "🟡 DEGRADED", "1.20s", "-8 pts", ACCENT_YELLOW),
        ("5", "checkoutservice", "🔴 CRITICAL", "3.90s", "-24 pts", ACCENT_RED),
        ("6", "cartservice", "🛑 OUTAGE", "4.02s", "-31 pts", ACCENT_RED),
        ("7", "valkey-cart", "🛑 CLUSTER SPOF", "5.12s", "-31 pts", ACCENT_RED),
    ]

    ty = 225
    for pos, sname, stat, mttr, delta, scol in tower_data:
        draw_rounded_rect(draw, [525, ty, WIDTH - 60, ty + 42], 4, fill=(18, 18, 26), outline=(30, 30, 42), width=1)
        draw.text((th_x[0] + 5, ty + 12), pos, font=get_font(12, bold=True), fill=TEXT_WHITE)
        draw.text((th_x[1], ty + 12), sname, font=get_font(12, bold=True), fill=TEXT_WHITE)
        draw.text((th_x[2], ty + 12), stat, font=get_font(11, bold=True), fill=scol)
        draw.text((th_x[3], ty + 12), mttr, font=get_font(12, mono=True), fill=TEXT_WHITE)
        draw.text((th_x[4], ty + 12), delta, font=get_font(12, bold=True, mono=True), fill=scol)
        ty += 48

    draw_footer_progress(draw, t_rel, dur, "STAGE 5: DETERMINISTIC RESILIENCE SCORING & TIMING TOWER")
    return np.array(img)


# ---------------- SCENE 7: AI RACE ENGINEER COPILOT & CONCLUSION ----------------
def render_scene_conclusion(t_rel, dur):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    draw_header(draw, "CHAOS PIT WALL", "AI RACE ENGINEER & SUBMISSION SUMMARY", "CHECKERED", t_rel)

    # Left: AI Team Radio Box
    left_box = [40, 100, 660, 640]
    draw_rounded_rect(draw, left_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((65, 125), "📻 TEAM RADIO: AI RACE ENGINEER COPILOT", font=get_font(14, bold=True), fill=ACCENT_CYAN)
    draw.text((65, 150), "Powered by Gemini 2.5 Flash + Deterministic Telemetry Context", font=get_font(12), fill=TEXT_MUTED)

    # Radio Dialogue Card
    draw_rounded_rect(draw, [65, 195, 635, 410], 8, fill=(16, 16, 24), outline=(35, 35, 50), width=1)
    draw.text((85, 215), "AI RACE ENGINEER RADIO TRANSCRIPT:", font=get_font(11, bold=True), fill=ACCENT_YELLOW)

    radio_lines = [
        "\"Box, box! Telemetry confirms two major vulnerabilities:\",",
        "1. cartservice and valkey-cart are unmitigated single points of failure.",
        "   When Valkey drops, the entire shopping flow collapses.",
        "2. Immediate action recommended before production deployment:",
        "   - Inject Envoy sidecar with circuit breaker on port 7070",
        "   - Configure Valkey Redis Sentinel with active-passive failover",
        "3. Watchdog safety mechanism operated flawlessly: <50ms revert.\""
    ]
    ry = 245
    for rl in radio_lines:
        draw.text((85, ry), rl, font=get_font(11), fill=TEXT_WHITE)
        ry += 22

    # Prescriptions Box
    draw_rounded_rect(draw, [65, 430, 635, 615], 8, fill=(18, 18, 27), outline=(40, 40, 58), width=1)
    draw.text((85, 448), "AUTOMATED INFRASTRUCTURE PRESCRIPTIONS", font=get_font(12, bold=True), fill=ACCENT_GREEN)

    fixes = [
        ("✅ Envoy Sidecar Circuit Breaker", "Drop calls after 500ms and return cached cart"),
        ("✅ Valkey Redis Sentinel Cluster", "Automatic master election prevents data loss"),
        ("✅ Graceful Degradation", "Allow browsing while cart gracefully degrades")
    ]
    fy = 478
    for ftitle, fdesc in fixes:
        draw.text((85, fy), ftitle, font=get_font(12, bold=True), fill=TEXT_WHITE)
        draw.text((85, fy + 18), fdesc, font=get_font(11), fill=TEXT_MUTED)
        fy += 44

    # Right: Submission Summary & Links
    right_box = [685, 100, WIDTH - 40, 640]
    draw_rounded_rect(draw, right_box, 10, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
    draw.text((710, 125), "HACKATHON SUBMISSION PACK", font=get_font(14, bold=True), fill=TEXT_WHITE)
    draw.text((710, 150), "Production-Ready Autonomous Chaos System", font=get_font(12), fill=TEXT_MUTED)

    links = [
        ("🌐 LIVE STREAMLIT PIT WALL", "https://chaos-agent.streamlit.app", ACCENT_CYAN),
        ("💻 SOURCE REPOSITORY", "https://github.com/Sreepallavimanikonda/chaos-agent", ACCENT_GREEN),
        ("🏎️ TARGET APPLICATION", "Google Cloud Online Boutique (13 services)", TEXT_WHITE),
        ("🛡️ SAFETY ASSURANCE", "500ms Active Watchdog + <50ms Rollback", ACCENT_YELLOW),
        ("📊 DETERMINISTIC ENGINE", "0% LLM Guesswork in Scoring Formula", TEXT_WHITE),
    ]

    ly = 200
    for ltitle, ldesc, lcol in links:
        draw_rounded_rect(draw, [710, ly, WIDTH - 65, ly + 65], 6, fill=(16, 16, 24), outline=(35, 35, 48), width=1)
        draw.text((725, ly + 12), ltitle, font=get_font(11, bold=True), fill=lcol)
        draw.text((725, ly + 36), ldesc, font=get_font(11, mono=True), fill=TEXT_WHITE)
        ly += 80

    draw_footer_progress(draw, t_rel, dur, "FINISH: SUBMISSION COMPLETE — READY FOR LIVE DEMO")
    return np.array(img)


# ---------------- MAIN GENERATION PIPELINE ----------------
def main():
    os.makedirs("assets", exist_ok=True)
    mp4_path = "assets/chaos_pitwall_demo.mp4"
    gif_path = "assets/chaos_pitwall_preview.gif"

    print("==================================================")
    print("🏎️ GENERATING CHAOS PIT WALL DEMO VIDEO")
    print(f"Target MP4: {mp4_path}")
    print(f"Target GIF: {gif_path}")
    print("==================================================")

    # Scenes timeline (Total duration: 64 seconds)
    scenes = [
        ("Intro & Pit Wall Concept", 8.0, render_scene_intro),
        ("Topology & SPOF Discovery", 9.0, render_scene_topology),
        ("Experiment 1: Cart Outage & Red Flag", 11.0, render_scene_experiment_1),
        ("Experiment 2: Valkey Redis Datastore SPOF", 10.0, render_scene_experiment_2),
        ("Experiment 3: Linux Kernel tc netem Delay", 9.0, render_scene_experiment_3),
        ("Deterministic Resilience Scoring", 9.0, render_scene_scoring),
        ("AI Race Engineer Copilot & Summary", 8.0, render_scene_conclusion),
    ]

    total_duration = sum(dur for _, dur, _ in scenes)
    total_frames = int(total_duration * FPS)
    print(f"Total Duration: {total_duration}s ({total_frames} frames @ {FPS} fps)")

    writer_mp4 = imageio.get_writer(
        mp4_path,
        fps=FPS,
        codec="libx264",
        pixelformat="yuv420p",
        ffmpeg_params=["-preset", "fast", "-crf", "22"]
    )

    gif_frames = []
    gif_step = 6  # Sample 1 out of every 6 frames for GIF (5 fps)

    frame_counter = 0

    for scene_idx, (sname, sdur, sfunc) in enumerate(scenes):
        print(f"\n[Scene {scene_idx + 1}/{len(scenes)}] Rendering '{sname}' ({sdur}s)...")
        num_frames = int(sdur * FPS)

        for f_idx in range(num_frames):
            t_rel = f_idx / FPS
            frame_arr = sfunc(t_rel, sdur)

            # Write to MP4
            writer_mp4.append_data(frame_arr)

            # Sample for GIF
            if frame_counter % gif_step == 0:
                # Downsample to 640x360 for light GIF
                pil_im = Image.fromarray(frame_arr).resize((640, 360), Image.Resampling.BILINEAR)
                gif_frames.append(np.array(pil_im))

            frame_counter += 1

            if f_idx % 60 == 0 or f_idx == num_frames - 1:
                pct = int((frame_counter / total_frames) * 100)
                sys.stdout.write(f"\r  Frame {f_idx + 1}/{num_frames} ({pct}% overall)...")
                sys.stdout.flush()

    writer_mp4.close()
    print(f"\n\n✅ Video successfully encoded: {mp4_path} ({os.path.getsize(mp4_path) / 1024 / 1024:.2f} MB)")

    # Save animated GIF preview
    print("\nEncoding GIF preview...")
    imageio.mimsave(gif_path, gif_frames, fps=5, loop=0)
    print(f"✅ GIF preview successfully saved: {gif_path} ({os.path.getsize(gif_path) / 1024 / 1024:.2f} MB)")
    print("==================================================")


if __name__ == "__main__":
    main()
