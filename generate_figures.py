import os
import tempfile

# Set non-interactive backend and writable cache directory for matplotlib
os.environ['MPLCONFIGDIR'] = tempfile.mkdtemp()
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.lines as mlines
from datetime import datetime, timedelta
import numpy as np

os.makedirs('doc_figures', exist_ok=True)

# ---------------------------------------------------------------------------
# Figure 1: SDLC Prototyping Model
# ---------------------------------------------------------------------------
def generate_sdlc():
    fig, ax = plt.subplots(figsize=(8.5, 5.0), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    # Color palette
    box_color = '#eff6ff'
    border_color = '#1d4ed8'
    text_color = '#0f172a'
    highlight_color = '#f0fdf4'
    highlight_border = '#16a34a'

    stages = [
        (1.2, 4.2, "1. Requirements Gathering\n& Threat Analysis\n(Acoustic/Visual specs)", box_color, border_color),
        (4.2, 4.2, "2. Quick Architectural\nDesign\n(ESP32 & Topology Model)", box_color, border_color),
        (7.2, 4.2, "3. Prototype Construction\n(YOLO + Dijkstra Fusion\n+ Sensor Telemetry)", box_color, border_color),
        (7.2, 1.8, "4. Prototype Evaluation\n& Simulation Drills\n(Adviser/Stakeholder)", '#fef2f2', '#dc2626'),
        (4.2, 1.8, "5. Prototype Refinement\n(Gate Isolation Logic,\nObstacle Routing)", highlight_color, highlight_border),
        (1.2, 1.8, "6. Final Operational Model\n(SENTINEL Deployment\n& Submission)", '#f8fafc', '#475569')
    ]

    for x, y, text, bg, border in stages:
        rect = patches.FancyBboxPatch((x - 1.0, y - 0.7), 2.0, 1.4,
                                      boxstyle="round,pad=0.1,rounding_size=0.15",
                                      facecolor=bg, edgecolor=border, linewidth=1.5, zorder=2)
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center', fontsize=9, fontweight='bold', color=text_color, zorder=3)

    # Forward arrows
    ax.annotate('', xy=(3.1, 4.2), xytext=(2.3, 4.2),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.8, mutation_scale=15))
    ax.annotate('', xy=(6.1, 4.2), xytext=(5.3, 4.2),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.8, mutation_scale=15))
    ax.annotate('', xy=(7.2, 2.6), xytext=(7.2, 3.4),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.8, mutation_scale=15))
    
    # Feedback loop: Evaluation -> Refinement
    ax.annotate('', xy=(5.3, 1.8), xytext=(6.1, 1.8),
                arrowprops=dict(arrowstyle="-|>", color='#dc2626', lw=1.8, mutation_scale=15))
    ax.text(5.7, 2.05, "Modifications Needed", ha='center', va='bottom', fontsize=8, color='#dc2626', fontweight='bold')

    # Refinement -> Construction loop
    ax.annotate('', xy=(6.5, 3.7), xytext=(4.7, 2.6),
                arrowprops=dict(arrowstyle="-|>", color='#16a34a', lw=1.8, mutation_scale=15, connectionstyle="arc3,rad=-0.2"))
    ax.text(5.3, 3.3, "Iterative Code Updates", ha='center', va='center', fontsize=8, color='#16a34a', fontweight='bold', rotation=30)

    # Evaluation -> Final Deployment
    ax.annotate('', xy=(2.3, 1.8), xytext=(3.1, 1.8),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.8, mutation_scale=15))
    ax.text(2.7, 2.05, "Requirements Met", ha='center', va='bottom', fontsize=8, color='#15803d', fontweight='bold')

    plt.tight_layout()
    plt.savefig('doc_figures/fig_sdlc.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_sdlc.png")

# ---------------------------------------------------------------------------
# Figure 2: Gantt Chart
# ---------------------------------------------------------------------------
def generate_gantt():
    fig, ax = plt.subplots(figsize=(10.0, 5.2), dpi=300)

    tasks = [
        ("A. Site Survey & Floor Plan Digitization", datetime(2026, 9, 1), 8, True),
        ("B. Microcontroller Acoustic Node Assembly (ESP32)", datetime(2026, 9, 9), 10, False),
        ("C. Visual Sensor & Camera Feed Setup", datetime(2026, 9, 9), 14, True),
        ("D. Campus Topological Graph Modeling", datetime(2026, 9, 15), 10, False),
        ("E. Threat Fusion Algorithm (YOLO + MediaPipe + Acoustic)", datetime(2026, 9, 23), 13, True),
        ("F. Interactive Command UI & Floor Plans", datetime(2026, 9, 25), 18, False),
        ("G. Dynamic Evacuation & Rerouting Engine (Dijkstra)", datetime(2026, 10, 6), 12, True),
        ("H. System Integration, API & WebSocket Middleware", datetime(2026, 10, 18), 7, True),
        ("I. Multi-Scenario Evacuation Testing & Validation", datetime(2026, 10, 25), 5, True),
        ("J. Baby Capstone Documentation & Stakeholder Review", datetime(2026, 10, 30), 4, True),
    ]

    y_pos = np.arange(len(tasks))
    start_base = datetime(2026, 9, 1)

    for i, (task, start_dt, duration, is_crit) in enumerate(reversed(tasks)):
        offset_days = (start_dt - start_base).days
        color = '#dc2626' if is_crit else '#2563eb'
        bar = ax.barh(i, duration, left=offset_days, height=0.55, align='center',
                      color=color, edgecolor='#0f172a', alpha=0.9, zorder=3)
        # Text label of duration
        ax.text(offset_days + duration / 2, i, f"{duration}d",
                ha='center', va='center', color='white', fontweight='bold', fontsize=8, zorder=4)

    task_labels = [t[0] for t in reversed(tasks)]
    ax.set_yticks(y_pos)
    ax.set_yticklabels(task_labels, fontsize=8.5, fontweight='medium')

    # Date formatting on X axis
    tick_offsets = [0, 7, 14, 21, 28, 35, 42, 49, 56, 63]
    tick_dates = [start_base + timedelta(days=d) for d in tick_offsets]
    tick_labels = [d.strftime('%b %d') for d in tick_dates]
    ax.set_xticks(tick_offsets)
    ax.set_xticklabels(tick_labels, fontsize=8.5)

    ax.set_xlabel('Project Implementation Timeline (September 1, 2026 - November 2, 2026)', fontsize=9.5, fontweight='bold', labelpad=8)
    ax.set_xlim(-1, 65)
    ax.grid(axis='x', linestyle='--', alpha=0.5, color='#94a3b8', zorder=1)

    # Custom legend
    crit_patch = patches.Patch(facecolor='#dc2626', edgecolor='#0f172a', label='Critical Path Activity')
    non_crit_patch = patches.Patch(facecolor='#2563eb', edgecolor='#0f172a', label='Non-Critical Task')
    ax.legend(handles=[crit_patch, non_crit_patch], loc='lower right', framealpha=0.9, fontsize=8.5)

    plt.tight_layout()
    plt.savefig('doc_figures/fig_gantt.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_gantt.png")

# ---------------------------------------------------------------------------
# Figure 3: PERT Network Chart
# ---------------------------------------------------------------------------
def generate_pert():
    fig, ax = plt.subplots(figsize=(10.5, 5.5), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.5)
    ax.axis('off')

    # Node data: (ID, Name, ES, EF, LS, LF, Slack, is_crit, x, y)
    nodes = [
        ("A", "Site Survey", 0, 8, 0, 8, 0, True, 1.2, 3.2),
        ("B", "ESP32 Assembly", 8, 18, 12, 22, 4, False, 3.2, 5.0),
        ("C", "Visual Sensors", 8, 22, 8, 22, 0, True, 3.2, 3.2),
        ("D", "Campus Graph", 8, 18, 24, 34, 16, False, 3.2, 1.4),
        ("E", "Threat Fusion", 22, 35, 22, 35, 0, True, 5.2, 3.2),
        ("F", "UI Dashboard", 8, 26, 33, 51, 25, False, 5.2, 1.4),
        ("G", "Dijkstra Engine", 35, 47, 35, 47, 0, True, 7.2, 3.2),
        ("H", "API Middleware", 47, 54, 47, 54, 0, True, 8.8, 3.2),
        ("I", "Drill Simulation", 54, 59, 54, 59, 0, True, 8.8, 1.6),
        ("J", "Documentation", 59, 63, 59, 63, 0, True, 10.2, 1.6)
    ]

    for nid, name, es, ef, ls, lf, slk, is_crit, x, y in nodes:
        border_col = '#dc2626' if is_crit else '#2563eb'
        bg_col = '#fef2f2' if is_crit else '#eff6ff'
        rect = patches.FancyBboxPatch((x - 0.7, y - 0.6), 1.4, 1.2,
                                      boxstyle="round,pad=0.08,rounding_size=0.12",
                                      facecolor=bg_col, edgecolor=border_col, linewidth=2.0 if is_crit else 1.2, zorder=3)
        ax.add_patch(rect)
        # Node text
        ax.text(x, y + 0.35, f"[{nid}] {name}", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#0f172a', zorder=4)
        ax.text(x, y + 0.05, f"ES:{es} | EF:{ef}", ha='center', va='center', fontsize=7, color='#1e293b', zorder=4)
        ax.text(x, y - 0.22, f"LS:{ls} | LF:{lf}", ha='center', va='center', fontsize=7, color='#1e293b', zorder=4)
        slack_text = f"Slack: {slk}d (CRIT)" if is_crit else f"Slack: {slk}d"
        ax.text(x, y - 0.45, slack_text, ha='center', va='center', fontsize=6.5,
                fontweight='bold', color='#dc2626' if is_crit else '#475569', zorder=4)

    # Connections
    edges = [
        ("A", "B", False), ("A", "C", True), ("A", "D", False), ("A", "F", False),
        ("B", "E", False), ("C", "E", True),
        ("D", "G", False), ("E", "G", True),
        ("G", "H", True), ("F", "H", False),
        ("H", "I", True), ("I", "J", True)
    ]

    pos_dict = {n[0]: (n[8], n[9]) for n in nodes}

    for u, v, is_crit in edges:
        x1, y1 = pos_dict[u]
        x2, y2 = pos_dict[v]
        dx, dy = x2 - x1, y2 - y1
        dist = np.sqrt(dx*dx + dy*dy)
        ux, uy = dx / dist, dy / dist
        start_x, start_y = x1 + ux * 0.72, y1 + uy * 0.62
        end_x, end_y = x2 - ux * 0.72, y2 - uy * 0.62

        col = '#dc2626' if is_crit else '#94a3b8'
        lw = 2.2 if is_crit else 1.2
        ax.annotate('', xy=(end_x, end_y), xytext=(start_x, start_y),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, mutation_scale=14, zorder=2))

    # Legend
    crit_line = mlines.Line2D([], [], color='#dc2626', lw=2.2, label='Critical Path (A -> C -> E -> G -> H -> I -> J = 63 Days)')
    non_crit = mlines.Line2D([], [], color='#94a3b8', lw=1.2, label='Non-Critical Task Dependency')
    ax.legend(handles=[crit_line, non_crit], loc='upper left', framealpha=0.9, fontsize=8.5)

    plt.tight_layout()
    plt.savefig('doc_figures/fig_pert.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_pert.png")

# ---------------------------------------------------------------------------
# Figure 4: System Context Diagram (Level 0 DFD)
# ---------------------------------------------------------------------------
def generate_context():
    fig, ax = plt.subplots(figsize=(8.8, 5.0), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis('off')

    # Central System
    center_circle = patches.Circle((5.0, 3.0), 1.4, facecolor='#eff6ff', edgecolor='#1d4ed8', linewidth=2.5, zorder=3)
    ax.add_patch(center_circle)
    ax.text(5.0, 3.25, "0.0\nSENTINEL SYSTEM", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#1e3a8a', zorder=4)
    ax.text(5.0, 2.7, "Acoustic-Visual Threat\nDetection & Dynamic\nEvacuation Simulator", ha='center', va='center', fontsize=7.5, color='#334155', zorder=4)

    # External Entities
    entities = [
        (1.4, 4.5, "ESP32 Acoustic Microcontroller Nodes\n(INMP441 Microphone Decibel Telemetry)", '#f8fafc', '#475569'),
        (1.4, 1.5, "Campus Surveillance IP Cameras\n(RTSP Video Feeds: Classrooms & Gates)", '#f8fafc', '#475569'),
        (8.6, 4.5, "Disaster Risk Reduction Officer /\nIncident Commander (Dashboard Admin)", '#fef2f2', '#dc2626'),
        (8.6, 1.5, "Classroom Occupants & Floor Wardens\n(Dynamic Egress Displays / Mobile UI)", '#f0fdf4', '#16a34a')
    ]

    for x, y, label, bg, border in entities:
        box = patches.FancyBboxPatch((x - 1.25, y - 0.65), 2.5, 1.3,
                                     boxstyle="round,pad=0.08,rounding_size=0.1",
                                     facecolor=bg, edgecolor=border, linewidth=1.8, zorder=3)
        ax.add_patch(box)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, fontweight='bold', color='#0f172a', zorder=4)

    # Inflow arrows
    # ESP32 -> System
    ax.annotate('', xy=(3.8, 3.6), xytext=(2.6, 4.5),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.5, mutation_scale=12))
    ax.text(2.9, 4.25, "Acoustic RMS Telemetry\n& Sound Peaks", ha='center', va='bottom', fontsize=7, color='#1e293b')

    # Camera -> System
    ax.annotate('', xy=(3.8, 2.4), xytext=(2.6, 1.5),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.5, mutation_scale=12))
    ax.text(2.9, 1.6, "Live Surveillance\nVideo Streams", ha='center', va='top', fontsize=7, color='#1e293b')

    # Admin <-> System
    ax.annotate('', xy=(5.9, 3.8), xytext=(7.4, 4.5),
                arrowprops=dict(arrowstyle="<|-", color='#dc2626', lw=1.5, mutation_scale=12))
    ax.text(6.9, 4.35, "Manual Overrides,\nGate Blocks, Drill Triggers", ha='center', va='bottom', fontsize=7, color='#dc2626')

    ax.annotate('', xy=(7.4, 4.1), xytext=(6.2, 3.4),
                arrowprops=dict(arrowstyle="-|>", color='#1e3a8a', lw=1.5, mutation_scale=12))
    ax.text(7.1, 3.5, "Live AI Scoreboard,\nReal-Time Alerts, Maps", ha='center', va='top', fontsize=7, color='#1e3a8a')

    # System -> Occupants
    ax.annotate('', xy=(7.4, 1.5), xytext=(6.2, 2.4),
                arrowprops=dict(arrowstyle="-|>", color='#16a34a', lw=1.5, mutation_scale=12))
    ax.text(7.0, 1.75, "Egress Path Directive,\nStairwell Guidance, Hold Alerts", ha='center', va='top', fontsize=7, color='#16a34a')

    plt.tight_layout()
    plt.savefig('doc_figures/fig_context.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_context.png")

# ---------------------------------------------------------------------------
# Figure 5: Data Flow Diagram Level 1 (DFD Level 1)
# ---------------------------------------------------------------------------
def generate_dfd1():
    fig, ax = plt.subplots(figsize=(9.8, 5.6), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.5)
    ax.axis('off')

    # Processes
    procs = [
        (2.0, 5.0, "1.0 Sensor Telemetry\nIngestion & Buffering", '#eff6ff', '#1d4ed8'),
        (5.5, 5.0, "2.0 Multi-Modal AI\nThreat Fusion", '#fef2f2', '#dc2626'),
        (5.5, 3.0, "3.0 Topological State\n& Obstacle Assessment", '#fef3c7', '#d97706'),
        (5.5, 1.0, "4.0 Dynamic Dijkstra\nEvacuation Routing", '#f0fdf4', '#16a34a'),
        (9.2, 1.0, "5.0 Command Dashboard\n& Guidance Broadcast", '#f8fafc', '#475569')
    ]

    for x, y, label, bg, border in procs:
        rect = patches.FancyBboxPatch((x - 1.1, y - 0.5), 2.2, 1.0,
                                      boxstyle="round,pad=0.08,rounding_size=0.15",
                                      facecolor=bg, edgecolor=border, linewidth=1.8, zorder=3)
        ax.add_patch(rect)
        ax.text(x, y, label, ha='center', va='center', fontsize=8, fontweight='bold', color='#0f172a', zorder=4)

    # Data stores
    stores = [
        (2.0, 3.0, "D1: Device & Sensor Registry"),
        (9.2, 5.0, "D2: Incident & Detection Logs"),
        (2.0, 1.0, "D3: Campus Topology Graph (36 Rooms)")
    ]

    for x, y, label in stores:
        # Open ended rectangle for DFD data store
        ax.plot([x - 1.1, x + 1.1], [y + 0.4, y + 0.4], color='#1e293b', lw=1.5, zorder=3)
        ax.plot([x - 1.1, x + 1.1], [y - 0.4, y - 0.4], color='#1e293b', lw=1.5, zorder=3)
        ax.plot([x - 1.1, x - 1.1], [y - 0.4, y + 0.4], color='#1e293b', lw=1.5, zorder=3)
        ax.text(x, y, label, ha='center', va='center', fontsize=7.5, fontweight='bold', color='#1e293b', zorder=4)

    # Flow arrows
    # 1.0 -> 2.0
    ax.annotate('', xy=(4.4, 5.0), xytext=(3.1, 5.0),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.5, mutation_scale=12))
    ax.text(3.75, 5.15, "Raw Telemetry\n& Frames", ha='center', va='bottom', fontsize=7)

    # D1 -> 1.0
    ax.annotate('', xy=(2.0, 4.5), xytext=(2.0, 3.4),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.2, mutation_scale=10))
    ax.text(1.3, 3.9, "Device Meta", ha='center', va='center', fontsize=7)

    # 2.0 -> D2
    ax.annotate('', xy=(8.1, 5.0), xytext=(6.6, 5.0),
                arrowprops=dict(arrowstyle="-|>", color='#dc2626', lw=1.5, mutation_scale=12))
    ax.text(7.35, 5.15, "Logged Threats\n& AI Confidence", ha='center', va='bottom', fontsize=7, color='#dc2626')

    # 2.0 -> 3.0
    ax.annotate('', xy=(5.5, 3.5), xytext=(5.5, 4.5),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.5, mutation_scale=12))
    ax.text(5.55, 4.0, "Verified Incidents\n(Index >= 70)", ha='left', va='center', fontsize=7)

    # 3.0 -> 4.0
    ax.annotate('', xy=(5.5, 1.5), xytext=(5.5, 2.5),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.5, mutation_scale=12))
    ax.text(5.55, 2.0, "Blocked Gates,\nStairs & Corridors", ha='left', va='center', fontsize=7)

    # D3 -> 4.0
    ax.annotate('', xy=(4.4, 1.0), xytext=(3.1, 1.0),
                arrowprops=dict(arrowstyle="-|>", color='#1e293b', lw=1.2, mutation_scale=10))
    ax.text(3.75, 1.15, "Node Adjacency\n& Path Weights", ha='center', va='bottom', fontsize=7)

    # 4.0 -> 5.0
    ax.annotate('', xy=(8.1, 1.0), xytext=(6.6, 1.0),
                arrowprops=dict(arrowstyle="-|>", color='#16a34a', lw=1.5, mutation_scale=12))
    ax.text(7.35, 1.15, "Optimal Routes\n& HOLD Directives", ha='center', va='bottom', fontsize=7, color='#16a34a')

    plt.tight_layout()
    plt.savefig('doc_figures/fig_dfd1.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_dfd1.png")

# ---------------------------------------------------------------------------
# Figure 6: System Operational Flowchart
# ---------------------------------------------------------------------------
def generate_flowchart():
    fig, ax = plt.subplots(figsize=(8.0, 10.0), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis('off')

    # Start
    start = patches.FancyBboxPatch((3.5, 13.0), 3.0, 0.6, boxstyle="round,pad=0.1,rounding_size=0.3",
                                  facecolor='#f1f5f9', edgecolor='#475569', lw=1.5)
    ax.add_patch(start)
    ax.text(5.0, 13.3, "START / SENSOR POLLING LOOP", ha='center', va='center', fontsize=8, fontweight='bold')

    # Step 1: Input
    step1 = patches.Polygon([[3.0, 11.9], [7.0, 11.9], [6.5, 12.6], [2.5, 12.6]],
                            facecolor='#eff6ff', edgecolor='#1d4ed8', lw=1.5)
    ax.add_patch(step1)
    ax.text(4.75, 12.25, "Acquire ESP32 Audio RMS & CCTV Video Frame", ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Step 2: Feature Extraction
    step2 = patches.Rectangle((2.5, 10.6), 5.0, 0.9, facecolor='#eff6ff', edgecolor='#1d4ed8', lw=1.5)
    ax.add_patch(step2)
    ax.text(5.0, 11.05, "Feature Extraction:\nAcoustic RMS + YOLO Object (Knife/Gun) + Pose Vectors", ha='center', va='center', fontsize=7.5)

    # Step 3: Compute Formula
    step3 = patches.Rectangle((2.2, 9.3), 5.6, 0.9, facecolor='#fef3c7', edgecolor='#d97706', lw=1.5)
    ax.add_patch(step3)
    ax.text(5.0, 9.75, "Calculate Composite Threat Index:\nT = 0.40(Object) + 0.35(Pose) + 0.25(Acoustic)", ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Step 4: Decision 1
    d1 = patches.Polygon([[5.0, 8.8], [7.2, 8.1], [5.0, 7.4], [2.8, 8.1]],
                         facecolor='#fef2f2', edgecolor='#dc2626', lw=1.5)
    ax.add_patch(d1)
    ax.text(5.0, 8.1, "Index >= 70.0 AND\nObject >= 60.0?", ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Critical path
    crit_box = patches.Rectangle((0.5, 6.2), 3.2, 0.8, facecolor='#fef2f2', edgecolor='#dc2626', lw=1.5)
    ax.add_patch(crit_box)
    ax.text(2.1, 6.6, "Flag Zone CRITICAL\n(Active Intruder Incident)", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#dc2626')

    # Warning Decision
    d2 = patches.Polygon([[5.0, 6.8], [7.0, 6.2], [5.0, 5.6], [3.0, 6.2]],
                         facecolor='#fef3c7', edgecolor='#d97706', lw=1.5)
    ax.add_patch(d2)
    ax.text(5.0, 6.2, "Index >= 30.0?", ha='center', va='center', fontsize=7.5, fontweight='bold')

    warn_box = patches.Rectangle((6.8, 4.8), 2.7, 0.7, facecolor='#fef3c7', edgecolor='#d97706', lw=1.5)
    ax.add_patch(warn_box)
    ax.text(8.15, 5.15, "Flag Zone WARNING\n(Caution State)", ha='center', va='center', fontsize=7, color='#b45309')

    norm_box = patches.Rectangle((3.6, 4.8), 2.8, 0.7, facecolor='#f0fdf4', edgecolor='#16a34a', lw=1.5)
    ax.add_patch(norm_box)
    ax.text(5.0, 5.15, "Flag Zone NORMAL\n(Baseline State)", ha='center', va='center', fontsize=7, color='#15803d')

    # Graph Evaluation
    step5 = patches.Rectangle((2.0, 3.4), 6.0, 0.9, facecolor='#eff6ff', edgecolor='#1d4ed8', lw=1.5)
    ax.add_patch(step5)
    ax.text(5.0, 3.85, "Campus Topological Assessment:\nIsolate Gate, Stairwell, or Corridor Nodes (Infinite Weight)", ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Dijkstra Execution
    step6 = patches.Rectangle((2.0, 2.1), 6.0, 0.9, facecolor='#f0fdf4', edgecolor='#16a34a', lw=1.5)
    ax.add_patch(step6)
    ax.text(5.0, 2.55, "Run Dijkstra Shortest Path for all 36 Classrooms:\nUpper floors with blocked egress -> Direct HOLD / Shelter-in-Place", ha='center', va='center', fontsize=7.5)

    # Output broadcast
    step7 = patches.Polygon([[2.2, 0.8], [7.8, 0.8], [7.3, 1.6], [1.7, 1.6]],
                            facecolor='#f8fafc', edgecolor='#475569', lw=1.5)
    ax.add_patch(step7)
    ax.text(4.75, 1.2, "Broadcast SVG Pathways & Directives via WebSocket", ha='center', va='center', fontsize=7.5, fontweight='bold')

    # Connecting Arrows
    def arrow(x1, y1, x2, y2, label=None, color='#1e293b'):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.5, mutation_scale=12))
        if label:
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            ax.text(mx + 0.15, my, label, fontsize=7, fontweight='bold', color=color)

    arrow(5.0, 13.0, 4.75, 12.6)
    arrow(4.75, 11.9, 5.0, 11.5)
    arrow(5.0, 10.6, 5.0, 10.2)
    arrow(5.0, 9.3, 5.0, 8.8)

    # Decision 1 branches
    arrow(2.8, 8.1, 2.1, 7.0, label="YES", color='#dc2626')
    arrow(5.0, 7.4, 5.0, 6.8, label="NO")

    # Decision 2 branches
    arrow(7.0, 6.2, 8.15, 5.5, label="YES", color='#d97706')
    arrow(5.0, 5.6, 5.0, 5.5, label="NO", color='#16a34a')

    # Merge into step 5
    arrow(2.1, 6.2, 3.5, 4.3, color='#dc2626')
    arrow(5.0, 4.8, 5.0, 4.3)
    arrow(8.15, 4.8, 6.5, 4.3)

    arrow(5.0, 3.4, 5.0, 3.0)
    arrow(5.0, 2.1, 4.75, 1.6)

    plt.tight_layout()
    plt.savefig('doc_figures/fig_flowchart.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_flowchart.png")

# ---------------------------------------------------------------------------
# Figure 7: Entity Relationship Diagram (ERD)
# ---------------------------------------------------------------------------
def generate_erd():
    fig, ax = plt.subplots(figsize=(10.5, 6.5), dpi=300)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    entities = [
        # (name, x, y, fields, border)
        ("BUILDING", 1.8, 6.2, ["building_code [PK]", "building_name", "total_floors", "rooms_per_floor"], '#1d4ed8'),
        ("CAMPUS_GATE", 1.8, 2.2, ["gate_id [PK]", "gate_name", "status", "adjacent_stair"], '#059669'),
        ("ROOM", 5.5, 6.2, ["room_id [PK]", "building_code [FK]", "floor_no", "room_no"], '#1d4ed8'),
        ("ROOM_DOOR", 9.5, 6.2, ["door_id [PK]", "room_id [FK]", "door_label", "corridor_node"], '#1d4ed8'),
        ("DEVICE", 5.5, 4.0, ["device_id [PK]", "building_code [FK]", "device_type", "covered_zone"], '#d97706'),
        ("THREAT_INCIDENT", 9.5, 4.0, ["incident_id [PK]", "started_at", "severity_level", "root_location"], '#dc2626'),
        ("THREAT_DETECTION", 9.5, 1.8, ["event_id [PK]", "incident_id [FK]", "device_id [FK]", "acoustic_rms", "object_conf", "threat_index"], '#dc2626'),
        ("EVACUATION_STATE", 5.5, 1.8, ["room_id [PK/FK]", "chosen_gate [FK]", "door_id [FK]", "path_sequence", "cost", "directive"], '#059669')
    ]

    for name, x, y, fields, border in entities:
        height = 0.35 + len(fields) * 0.28
        width = 2.4
        rect = patches.FancyBboxPatch((x - width/2, y - height/2), width, height,
                                      boxstyle="round,pad=0.05,rounding_size=0.1",
                                      facecolor='#ffffff', edgecolor=border, lw=1.8, zorder=3)
        ax.add_patch(rect)
        # Header banner
        header = patches.Rectangle((x - width/2, y + height/2 - 0.35), width, 0.35,
                                   facecolor=border, edgecolor=border, zorder=4)
        ax.add_patch(header)
        ax.text(x, y + height/2 - 0.18, name, ha='center', va='center', fontsize=8, fontweight='bold', color='white', zorder=5)

        for idx, fld in enumerate(fields):
            fy = y + height/2 - 0.55 - idx * 0.28
            is_pk = "[PK]" in fld
            is_fk = "[FK]" in fld
            col = '#dc2626' if is_pk else ('#2563eb' if is_fk else '#1e293b')
            weight = 'bold' if (is_pk or is_fk) else 'normal'
            ax.text(x - width/2 + 0.15, fy, fld, ha='left', va='center', fontsize=6.8, color=col, fontweight=weight, zorder=5)

    # Relationships Lines with Crow's Foot annotations
    def rel(x1, y1, x2, y2, card1, card2, col='#475569'):
        ax.plot([x1, x2], [y1, y2], color=col, lw=1.5, zorder=2)
        ax.text(x1, y1, card1, fontsize=7.5, fontweight='bold', color=col)
        ax.text(x2, y2, card2, fontsize=7.5, fontweight='bold', color=col)

    rel(3.0, 6.2, 4.3, 6.2, "1", "N")          # BUILDING -> ROOM
    rel(6.7, 6.2, 8.3, 6.2, "1", "N")          # ROOM -> DOOR
    rel(2.2, 5.3, 4.5, 4.4, "1", "N")          # BUILDING -> DEVICE
    rel(6.7, 4.0, 8.3, 4.0, "1", "N")          # INCIDENT -> DETECTION
    rel(6.7, 3.6, 8.3, 2.3, "1", "N")          # DEVICE -> DETECTION
    rel(5.5, 5.3, 5.5, 2.7, "1", "1")          # ROOM -> EVACUATION_STATE
    rel(3.0, 2.2, 4.3, 2.0, "1", "N")          # GATE -> EVACUATION_STATE

    plt.tight_layout()
    plt.savefig('doc_figures/fig_erd.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_erd.png")

# ---------------------------------------------------------------------------
# Figure 8: Use-Case Diagram
# ---------------------------------------------------------------------------
def generate_usecase():
    fig, ax = plt.subplots(figsize=(9.5, 6.0), dpi=300)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # System boundary box
    sys_rect = patches.FancyBboxPatch((3.0, 0.4), 5.2, 6.2, boxstyle="round,pad=0.1,rounding_size=0.15",
                                      facecolor='#f8fafc', edgecolor='#64748b', lw=1.8, zorder=1)
    ax.add_patch(sys_rect)
    ax.text(5.6, 6.35, "SENTINEL Campus Safety System", ha='center', va='center', fontsize=9.5, fontweight='bold', color='#1e293b')

    # Actors
    def draw_actor(x, y, name, col):
        # Head
        ax.add_patch(patches.Circle((x, y + 0.35), 0.18, facecolor='#ffffff', edgecolor=col, lw=1.8, zorder=3))
        # Body
        ax.plot([x, x], [y + 0.17, y - 0.25], color=col, lw=1.8, zorder=3)
        # Arms
        ax.plot([x - 0.25, x + 0.25], [y + 0.05, y + 0.05], color=col, lw=1.8, zorder=3)
        # Legs
        ax.plot([x, x - 0.22], [y - 0.25, y - 0.55], color=col, lw=1.8, zorder=3)
        ax.plot([x, x + 0.22], [y - 0.25, y - 0.55], color=col, lw=1.8, zorder=3)
        ax.text(x, y - 0.75, name, ha='center', va='top', fontsize=7.5, fontweight='bold', color=col)

    draw_actor(1.2, 4.8, "Campus DRRM Officer /\nGate Security Guard", '#1d4ed8')
    draw_actor(1.2, 2.0, "School Principal /\nIncident Commander", '#dc2626')
    draw_actor(9.8, 4.2, "ESP32 Sensor Daemon\n& Camera IP Streams", '#059669')

    use_cases = [
        (5.6, 5.7, "UC-01: Monitor Real-Time CCTV\n& Sensor Feeds"),
        (5.6, 5.0, "UC-02: Ingest Multi-Modal Threat Signals\n(Acoustic + Visual)"),
        (5.6, 4.3, "UC-03: Assess AI Threat Index\n& Trigger Alarm Level"),
        (5.6, 3.6, "UC-04: Dynamically Reroute Classrooms\n(Gate & Stair Evacuation)"),
        (5.6, 2.9, "UC-05: Execute Manual Gate / Stair\nClosure Override"),
        (5.6, 2.2, "UC-06: Trigger Prebaked Scenario Drills\n(Simulation Testing)"),
        (5.6, 1.5, "UC-07: Broadcast Emergency Directives\n(Egress / HOLD Lockdown)"),
        (5.6, 0.8, "UC-08: Review Room Egress Card\n& Forensic Incident Audit Log")
    ]

    for x, y, label in use_cases:
        ellipse = patches.Ellipse((x, y), 3.8, 0.55, facecolor='#ffffff', edgecolor='#1e3a8a', lw=1.3, zorder=3)
        ax.add_patch(ellipse)
        ax.text(x, y, label, ha='center', va='center', fontsize=7, fontweight='bold', color='#1e3a8a', zorder=4)

    # Actor-UseCase connections
    def link(x1, y1, x2, y2, col='#475569'):
        ax.plot([x1, x2], [y1, y2], color=col, lw=1.2, zorder=2)

    # DRRM Officer links
    link(1.6, 4.8, 3.7, 5.7)
    link(1.6, 4.8, 3.7, 2.9)
    link(1.6, 4.8, 3.7, 0.8)

    # Incident Commander links
    link(1.6, 2.0, 3.7, 5.7)
    link(1.6, 2.0, 3.7, 2.9)
    link(1.6, 2.0, 3.7, 2.2)
    link(1.6, 2.0, 3.7, 1.5)
    link(1.6, 2.0, 3.7, 0.8)

    # Edge Daemon links
    link(9.4, 4.2, 7.5, 5.0)
    link(9.4, 4.2, 7.5, 4.3)
    link(9.4, 4.2, 7.5, 3.6)

    plt.tight_layout()
    plt.savefig('doc_figures/fig_usecase.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Generated fig_usecase.png")

if __name__ == '__main__':
    generate_sdlc()
    generate_gantt()
    generate_pert()
    generate_context()
    generate_dfd1()
    generate_flowchart()
    generate_erd()
    generate_usecase()
    print("All 8 figures generated successfully.")
