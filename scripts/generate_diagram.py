import random
import os
import json
import subprocess
import math

# Set seed for reproducible sketchy lines and Excalidraw seeds
random.seed(42)

def escape_xml(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ------------------ SVG SKETCHY RENDER HELPERS ------------------
def sketchy_line(x1, y1, x2, y2, overshoot=4, wobble=1.5):
    dx = x2 - x1
    dy = y2 - y1
    length = (dx*dx + dy*dy) ** 0.5
    if length == 0:
        return ""
    
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    
    paths = []
    for _ in range(2): # Double stroke for sketchy feel
        os_start = random.uniform(-overshoot, overshoot/2)
        os_end = random.uniform(-overshoot/2, overshoot)
        
        sx = x1 - ux * os_start
        sy = y1 - uy * os_start
        ex = x2 + ux * os_end
        ey = y2 + uy * os_end
        
        # Add a midpoint with a small normal offset
        mid_t = random.uniform(0.3, 0.7)
        mid_x = sx + dx * mid_t + nx * random.uniform(-wobble, wobble)
        mid_y = sy + dy * mid_t + ny * random.uniform(-wobble, wobble)
        
        paths.append(f"M {sx:.1f},{sy:.1f} Q {mid_x:.1f},{mid_y:.1f} {ex:.1f},{ey:.1f}")
        
    return " ".join(paths)

def sketchy_rect(x, y, w, h, overshoot=4, wobble=1.5):
    top = sketchy_line(x, y, x + w, y, overshoot, wobble)
    right = sketchy_line(x + w, y, x + w, y + h, overshoot, wobble)
    bottom = sketchy_line(x + w, y + h, x, y + h, overshoot, wobble)
    left = sketchy_line(x, y + h, x, y, overshoot, wobble)
    return " ".join([top, right, bottom, left])

def sketchy_ellipse(cx, cy, rx, ry, num_points=36, wobble=1.2, loops=2):
    paths = []
    for _ in range(loops):
        points = []
        start_angle = random.uniform(0, 2*math.pi)
        for i in range(num_points + 1):
            angle = start_angle + (i / num_points) * 2 * math.pi
            r_offset = random.uniform(-wobble, wobble)
            x = cx + (rx + r_offset) * math.cos(angle)
            y = cy + (ry + r_offset) * math.sin(angle)
            points.append(f"{x:.1f},{y:.1f}")
        paths.append("M " + points[0] + " " + " ".join(f"L {p}" for p in points[1:]))
    return " ".join(paths)

def sketchy_diamond(cx, cy, w, h, overshoot=4, wobble=1.5):
    t = (cx, cy - h/2)
    r = (cx + w/2, cy)
    b = (cx, cy + h/2)
    l = (cx - w/2, cy)
    top_right = sketchy_line(t[0], t[1], r[0], r[1], overshoot, wobble)
    right_bottom = sketchy_line(r[0], r[1], b[0], b[1], overshoot, wobble)
    bottom_left = sketchy_line(b[0], b[1], l[0], l[1], overshoot, wobble)
    left_top = sketchy_line(l[0], l[1], t[0], t[1], overshoot, wobble)
    return " ".join([top_right, right_bottom, bottom_left, left_top])

def sketchy_arrow(x1, y1, x2, y2, overshoot=3, wobble=1.0):
    line = sketchy_line(x1, y1, x2, y2, overshoot, wobble)
    dx = x2 - x1
    dy = y2 - y1
    length = (dx*dx + dy*dy) ** 0.5
    if length == 0:
        return line
    
    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    
    arrow_len = 12
    # Left barb
    lx = x2 - ux * arrow_len + nx * (arrow_len * 0.4)
    ly = y2 - uy * arrow_len + ny * (arrow_len * 0.4)
    barb1 = sketchy_line(x2, y2, lx, ly, overshoot=2, wobble=0.5)
    
    # Right barb
    rx = x2 - ux * arrow_len - nx * (arrow_len * 0.4)
    ry = y2 - uy * arrow_len - ny * (arrow_len * 0.4)
    barb2 = sketchy_line(x2, y2, rx, ry, overshoot=2, wobble=0.5)
    
    return " ".join([line, barb1, barb2])

def draw_svg_text(svg, lines, cx, cy, line_height=16, is_title=True, text_anchor="middle"):
    class_name = "label-title" if is_title else "label-text"
    num_lines = len(lines)
    start_y = cy - (num_lines - 1) * line_height / 2
    
    # Adjust for left alignment coordinates
    x_pos = cx
    
    for i, line in enumerate(lines):
        y_pos = start_y + i * line_height
        
        # Apply special styling to redacted lines or code fragments
        style_attr = ""
        if "REDACTED" in line or line.startswith("\"") or line.startswith("class:") or line.startswith("status:"):
            style_attr = 'style="font-family: monospace; font-size: 10px; fill: #4a8f5c; font-weight: bold;"'
        elif line.startswith("-") or line.startswith("1.") or line.startswith("2.") or line.startswith("3.") or line.startswith("4.") or line.startswith("5."):
            # Bullet point alignment adjustments if needed
            pass
            
        svg.append(f'  <text x="{x_pos:.1f}" y="{y_pos:.1f}" class="{class_name}" text-anchor="{text_anchor}" {style_attr}>{escape_xml(line)}</text>')

# ------------------ EXCALIDRAW JSON HELPERS ------------------
def make_excalidraw_rect(node_id, text, cx, cy, w, h, bg_color, textAlign="center"):
    seed = random.randint(100000, 999999)
    rect_id = f"rect_{node_id}"
    text_id = f"text_{node_id}"
    
    x = cx - w / 2
    y = cy - h / 2
    
    rect_elem = {
        "id": rect_id,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": bg_color,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "roundness": { "type": 3 },
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": [{"id": text_id, "type": "text"}],
        "updated": 1716300000000,
        "link": None,
        "locked": False
    }
    
    num_lines = len(text.split("\n"))
    text_height = num_lines * 16
    
    if textAlign == "left":
        text_x = x + 15
        text_w = w - 30
    else:
        text_x = x + 10
        text_w = w - 20
        
    text_elem = {
        "id": text_id,
        "type": "text",
        "x": text_x,
        "y": y + (h - text_height) / 2,
        "width": text_w,
        "height": text_height,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "roundness": None,
        "seed": seed + 2,
        "version": 1,
        "versionNonce": seed + 3,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": 12,
        "fontFamily": 1, # Handwritten Excalidraw font
        "textAlign": textAlign,
        "verticalAlign": "middle",
        "containerId": rect_id,
        "originalText": text,
        "lineHeight": 1.2
    }
    
    return [rect_elem, text_elem]

def make_excalidraw_ellipse(node_id, text, cx, cy, w, h, bg_color):
    seed = random.randint(100000, 999999)
    ellipse_id = f"ellipse_{node_id}"
    text_id = f"text_{node_id}"
    
    x = cx - w / 2
    y = cy - h / 2
    
    ellipse_elem = {
        "id": ellipse_id,
        "type": "ellipse",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": bg_color,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1.2,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "roundness": { "type": 3 },
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": [{"id": text_id, "type": "text"}],
        "updated": 1716300000000,
        "link": None,
        "locked": False
    }
    
    num_lines = len(text.split("\n"))
    text_height = num_lines * 14
    
    text_elem = {
        "id": text_id,
        "type": "text",
        "x": x + 10,
        "y": y + (h - text_height) / 2,
        "width": w - 20,
        "height": text_height,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "roundness": None,
        "seed": seed + 2,
        "version": 1,
        "versionNonce": seed + 3,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": 12,
        "fontFamily": 1, # Handwritten
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": ellipse_id,
        "originalText": text,
        "lineHeight": 1.2
    }
    
    return [ellipse_elem, text_elem]

def make_excalidraw_diamond(node_id, text, cx, cy, w, h, bg_color):
    seed = random.randint(100000, 999999)
    diamond_id = f"diamond_{node_id}"
    text_id = f"text_{node_id}"
    
    x = cx - w / 2
    y = cy - h / 2
    
    diamond_elem = {
        "id": diamond_id,
        "type": "diamond",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": bg_color,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1.5,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": [{"id": text_id, "type": "text"}],
        "updated": 1716300000000,
        "link": None,
        "locked": False
    }
    
    num_lines = len(text.split("\n"))
    text_height = num_lines * 14
    
    text_elem = {
        "id": text_id,
        "type": "text",
        "x": x + 15,
        "y": y + (h - text_height) / 2,
        "width": w - 30,
        "height": text_height,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [f"group_{node_id}"],
        "roundness": None,
        "seed": seed + 2,
        "version": 1,
        "versionNonce": seed + 3,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": 11,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": diamond_id,
        "originalText": text,
        "lineHeight": 1.2
    }
    
    return [diamond_elem, text_elem]

def make_excalidraw_arrow(arrow_id, x1, y1, x2, y2, strokeColor="#ffffff"):
    seed = random.randint(100000, 999999)
    dx = x2 - x1
    dy = y2 - y1
    
    return {
        "id": f"arrow_{arrow_id}",
        "type": "arrow",
        "x": x1,
        "y": y1,
        "width": abs(dx),
        "height": abs(dy),
        "angle": 0,
        "strokeColor": strokeColor,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1.5,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 80,
        "groupIds": [],
        "roundness": { "type": 2 },
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "points": [
            [0, 0],
            [dx, dy]
        ],
        "startBinding": None,
        "endBinding": None,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": "arrow"
    }

def make_excalidraw_line(line_id, x1, y1, x2, y2, strokeColor="#ffffff", strokeStyle="solid"):
    seed = random.randint(100000, 999999)
    dx = x2 - x1
    dy = y2 - y1
    return {
        "id": f"line_{line_id}",
        "type": "line",
        "x": x1,
        "y": y1,
        "width": abs(dx),
        "height": abs(dy),
        "angle": 0,
        "strokeColor": strokeColor,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": strokeStyle,
        "roughness": 1,
        "opacity": 80,
        "groupIds": [],
        "roundness": None,
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "points": [
            [0, 0],
            [dx, dy]
        ],
        "startBinding": None,
        "endBinding": None,
        "lastCommittedPoint": None,
        "startArrowhead": None,
        "endArrowhead": None
    }

def make_excalidraw_boundary(boundary_id, label, x, y, w, h):
    seed = random.randint(100000, 999999)
    rect_id = f"boundary_{boundary_id}"
    text_id = f"boundary_text_{boundary_id}"
    
    rect_elem = {
        "id": rect_id,
        "type": "rectangle",
        "x": x,
        "y": y,
        "width": w,
        "height": h,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1.5,
        "strokeStyle": "dashed",
        "roughness": 1.5,
        "opacity": 40,
        "groupIds": [],
        "roundness": { "type": 3 },
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": [],
        "updated": 1716300000000,
        "link": None,
        "locked": False
    }
    
    text_elem = {
        "id": text_id,
        "type": "text",
        "x": x + 15,
        "y": y + 15,
        "width": w - 30,
        "height": 20,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 90,
        "groupIds": [],
        "roundness": None,
        "seed": seed + 2,
        "version": 1,
        "versionNonce": seed + 3,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "text": label,
        "fontSize": 14,
        "fontFamily": 1,
        "textAlign": "left",
        "verticalAlign": "top",
        "containerId": None,
        "originalText": label,
        "lineHeight": 1.2
    }
    
    return [rect_elem, text_elem]

def make_excalidraw_circle_marker(marker_id, text, cx, cy, diameter, bg_color):
    seed = random.randint(100000, 999999)
    ellipse_id = f"marker_{marker_id}"
    text_id = f"marker_text_{marker_id}"
    
    x = cx - diameter / 2
    y = cy - diameter / 2
    
    ellipse_elem = {
        "id": ellipse_id,
        "type": "ellipse",
        "x": x,
        "y": y,
        "width": diameter,
        "height": diameter,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": bg_color,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [f"group_{marker_id}"],
        "seed": seed,
        "version": 1,
        "versionNonce": seed + 1,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False
    }
    
    num_lines = len(text.split("\n"))
    text_height = num_lines * 14
    
    text_elem = {
        "id": text_id,
        "type": "text",
        "x": cx - 80,
        "y": cy + 15,
        "width": 160,
        "height": text_height,
        "angle": 0,
        "strokeColor": "#ffffff",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 90,
        "groupIds": [f"group_{marker_id}"],
        "roundness": None,
        "seed": seed + 2,
        "version": 1,
        "versionNonce": seed + 3,
        "isDeleted": False,
        "boundElements": None,
        "updated": 1716300000000,
        "link": None,
        "locked": False,
        "text": text,
        "fontSize": 10,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "containerId": None,
        "originalText": text,
        "lineHeight": 1.2
    }
    
    return [ellipse_elem, text_elem]

def save_excalidraw_file(elements, output_path):
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "transparent",
            "theme": "light",
            "gridSize": None,
            "exportBackground": False
        },
        "files": {}
    }
    with open(output_path, "w") as f:
        json.dump(scene, f, indent=2)
    print(f"Successfully generated Excalidraw JSON file at: {output_path}")

# ------------------ DIAGRAM GENERATORS ------------------
def create_architecture_diagram():
    svg_width = 1600
    svg_height = 1040
    
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="100%" height="100%" style="background: transparent;">')
    svg.append("""  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Architects+Daughter&amp;family=Comic+Neue:wght@400;700&amp;display=swap');
      
      .main-title {
        font-family: 'Architects Daughter', 'Comic Neue', sans-serif;
        font-size: 24px;
        font-weight: bold;
        fill: #ffffff;
      }
      .main-subtitle {
        font-family: 'Architects Daughter', 'Comic Neue', sans-serif;
        font-size: 13px;
        fill: #ffffff;
        font-style: italic;
      }
      
      .label-title {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 12.5px;
        font-weight: bold;
        fill: #ffffff;
      }
      
      .label-text {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 11px;
        fill: #ffffff;
      }
      
      .sketch-stroke {
        stroke: #ffffff;
        stroke-width: 1.8;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.85;
      }
      
      .sketch-stroke-arrow {
        stroke: #ffffff;
        stroke-width: 1.5;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.75;
      }
      
      .sketch-fill {
        stroke: none;
        opacity: 0.15;
      }
      
      .group-label {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 13.5px;
        font-weight: bold;
        fill: #ffffff;
      }
    </style>
  </defs>""")
    
    # Title Block
    svg.append(f'  <text x="30" y="45" class="main-title">adopt-redthread — context compiler &amp; security assurance bridge for AI pentesting</text>')
    svg.append(f'  <text x="30" y="65" class="main-subtitle">Visual thesis: Raw runtime evidence is hostile &amp; private; only sanitized, mapped, and boundary-checked context packages may pass to LLMs &amp; agents.</text>')
    
    excalidraw_elements = []
    
    # ------------------ STEP ZONES (1 to 4) ------------------
    # Zone boundaries (x, y, w, h)
    zones = [
        ("raw_ingest", "1. Raw Ingestion Lane (Untrusted/Hostile)", 20, 90, 350, 480, "#cba6f7", "#e0d3f7"),
        ("bridge_gate", "2. Sanitization &amp; Context Bridge (adopt-redthread)", 390, 90, 440, 480, "#fab387", "#fadca5"),
        ("handoff", "3. Sanitized Handoff (Pentest Context Package)", 850, 90, 370, 480, "#89b4fa", "#c6daf7"),
        ("assurance", "4. Downstream Assurance &amp; Agent", 1240, 90, 340, 480, "#a6e3a1", "#c8ebd0")
    ]
    
    for zid, title, zx, zy, zw, zh, color_svg, color_exc in zones:
        # SVG boundary
        svg.append(f'  <rect x="{zx}" y="{zy}" width="{zw}" height="{zh}" rx="8" fill="{color_svg}" class="sketch-fill" />')
        boundary_path = sketchy_rect(zx, zy, zw, zh, overshoot=6, wobble=2)
        svg.append(f'  <path d="{boundary_path}" class="sketch-stroke-arrow" stroke-dasharray="5,5" style="opacity: 0.5;" />')
        svg.append(f'  <text x="{zx + 15}" y="{zy + 25}" class="group-label">{title}</text>')
        
        # Excalidraw boundary
        raw_title = title.replace("&amp;", "&")
        excalidraw_elements.extend(make_excalidraw_boundary(zid, raw_title, zx, zy, zw, zh))
        
    # ------------------ ZONE 1 CONTENT ------------------
    # Input Ovals
    inputs = [
        ("har", ["HAR Capture"], 100, 175, 110, 45, "#f5c2e7"),
        ("zapi", ["ZAPI Export"], 200, 175, 110, 45, "#89b4fa"),
        ("noui", ["NoUI/MCP"], 290, 175, 110, 45, "#89dceb"),
        ("action", ["Action Catalog"], 195, 235, 160, 45, "#a6e3a1")
    ]
    for nid, lines, cx, cy, w, h, color in inputs:
        x = cx - w/2
        y = cy - h/2
        svg.append(f'  <ellipse cx="{cx}" cy="{cy}" rx="{w/2}" ry="{h/2}" fill="{color}" class="sketch-fill" />')
        ellipse_path = sketchy_ellipse(cx, cy, w/2, h/2)
        svg.append(f'  <path d="{ellipse_path}" class="sketch-stroke" />')
        draw_svg_text(svg, lines, cx, cy, is_title=True)
        
        raw_text = "\n".join(lines)
        excalidraw_elements.extend(make_excalidraw_ellipse(nid, raw_text, cx, cy, w, h, color))
        
    # Ingestion Adapters
    svg.append(f'  <rect x="50" y="280" width="290" height="65" rx="6" fill="#b4befe" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(50, 280, 290, 65)}" class="sketch-stroke" />')
    draw_svg_text(svg, ["Ingestion Adapters", "(noise filters, app dedupes)"], 195, 312.5, is_title=True)
    excalidraw_elements.extend(make_excalidraw_rect("ingest_adapters", "Ingestion Adapters\n(noise filters, app dedupes)", 195, 312.5, 290, 65, "#b4befe"))
    
    # Hostile Warnings
    lines_hostile = [
        "Hostile Capture Inputs (High Risk):",
        "- Live Session Cookies &amp; Auth Headers",
        "- Production Tokens &amp; Credentials",
        "- Raw Request/Response Bodies",
        "- Sensitive PII &amp; Account Details"
    ]
    svg.append(f'  <rect x="50" y="365" width="290" height="110" rx="6" fill="#f38ba8" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(50, 365, 290, 110)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_hostile, 65, 420, line_height=16, is_title=False, text_anchor="start")
    
    raw_hostile = "\n".join(lines_hostile).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("hostile_warn", raw_hostile, 195, 420, 290, 110, "#f38ba8", textAlign="left"))
    
    # Redacted Code Box
    svg.append(f'  <rect x="60" y="495" width="270" height="45" rx="4" fill="#1e1e2e" />')
    svg.append(f'  <path d="{sketchy_rect(60, 495, 270, 45)}" class="sketch-stroke" style="stroke: #a6adc8;" />')
    draw_svg_text(svg, ['"cookie": "session_id=prod_sec..." (REDACTED)'], 195, 517.5, is_title=False)
    excalidraw_elements.extend(make_excalidraw_rect("code_redact", '"cookie": "session_id=prod_sec..." (REDACTED)', 195, 517.5, 270, 45, "#1e1e2e"))
    
    # ------------------ ZONE 2 CONTENT ------------------
    # Column/Row 2x3 diamond grid in Zone 2
    steps = [
        ("step1", ["1. Ingest Sanitizer", "noise filters &amp;", "deduplication"], 460, 170, 130, 70, "#f5c2e7"),
        ("step2", ["2. Traffic Filter", "identifies active", "app endpoints"], 610, 170, 130, 70, "#89b4fa"),
        ("step3", ["3. Privacy Audit", "redacts credentials", "&amp; drops PII"], 760, 170, 130, 70, "#f38ba8"),
        ("step4", ["4. Auth &amp; Write Tag", "classifies mutating", "&amp; destructive"], 460, 290, 130, 70, "#fab387"),
        ("step5", ["5. Context Compiler", "maps clean schema", "without secrets"], 610, 290, 130, 70, "#a6e3a1"),
        ("step6", ["6. Hypothesis Gen", "marks hypotheses", "never overclaims"], 760, 290, 130, 70, "#f9e2af")
    ]
    for nid, lines, cx, cy, w, h, color in steps:
        svg.append(f'  <polygon points="{cx},{cy - h/2} {cx + w/2},{cy} {cx},{cy + h/2} {cx - w/2},{cy}" fill="{color}" class="sketch-fill" />')
        diamond_path = sketchy_diamond(cx, cy, w, h)
        svg.append(f'  <path d="{diamond_path}" class="sketch-stroke" />')
        draw_svg_text(svg, lines, cx, cy, is_title=True)
        
        raw_text = "\n".join(lines).replace("&amp;", "&")
        excalidraw_elements.extend(make_excalidraw_diamond(nid, raw_text, cx, cy, w, h, color))
        
    # Code block at bottom of Zone 2
    lines_json_output = [
        "class: \"requires_judge_confirmation: true\"",
        "status: \"not_a_finding: true\"",
        "\"auth_requirements\": { \"read_only\": true }"
    ]
    svg.append(f'  <rect x="420" y="405" width="380" height="80" rx="4" fill="#1e1e2e" />')
    svg.append(f'  <path d="{sketchy_rect(420, 405, 380, 80)}" class="sketch-stroke" style="stroke: #a6adc8;" />')
    draw_svg_text(svg, lines_json_output, 435, 445, line_height=16, is_title=False, text_anchor="start")
    
    raw_json_output = "\n".join(lines_json_output)
    excalidraw_elements.extend(make_excalidraw_rect("bridge_code", raw_json_output, 610, 445, 380, 80, "#1e1e2e", textAlign="left"))
    
    # ------------------ ZONE 3 CONTENT ------------------
    # Package Content Box
    lines_pkg = [
        "Pentest Context Package v0 (JSON)",
        "- manifest.json &amp; package_summary.json",
        "- endpoint_inventory.json (clean schemas)",
        "- workflow_map.json (replayed sequences)",
        "- attack_surface_hypotheses.json",
        "- auth_requirements.json",
        "- missing_context.json"
    ]
    svg.append(f'  <rect x="870" y="140" width="330" height="190" rx="6" fill="#b4befe" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(870, 140, 330, 190)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_pkg, 885, 235, line_height=18, is_title=False, text_anchor="start")
    
    raw_pkg = "\n".join(lines_pkg).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("pkg_content", raw_pkg, 1035, 235, 330, 190, "#b4befe", textAlign="left"))
    
    # Human markdown box
    lines_md = [
        "Human-Readable Review Packet",
        "- reviewer_packet.md (Sanitized view)",
        "- pentest_agent_brief.md (Agent prompts)"
    ]
    svg.append(f'  <rect x="870" y="345" width="330" height="80" rx="6" fill="#a6e3a1" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(870, 345, 330, 80)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_md, 885, 385, line_height=18, is_title=False, text_anchor="start")
    
    raw_md = "\n".join(lines_md)
    excalidraw_elements.extend(make_excalidraw_rect("md_briefs", raw_md, 1035, 385, 330, 80, "#a6e3a1", textAlign="left"))
    
    # Opt-in auth box
    lines_optin = [
        "Opt-in Auth &amp; Write Bundles (Separate)",
        "- approved_auth_bundle (scoped reads)",
        "- approved_write_bundle (reviewed writes)",
        "- Pinned env scopes, never logged/committed"
    ]
    svg.append(f'  <rect x="870" y="440" width="330" height="110" rx="6" fill="#fab387" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(870, 440, 330, 110)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_optin, 885, 495, line_height=18, is_title=False, text_anchor="start")
    
    raw_optin = "\n".join(lines_optin).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("optin_bundles", raw_optin, 1035, 495, 330, 110, "#fab387", textAlign="left"))
    
    # ------------------ ZONE 4 CONTENT ------------------
    # Agent Briefing
    lines_agent = [
        "Specialized Pentest Agent",
        "- Consumes sanitized Context Briefs",
        "- Selects targeted adversarial probes",
        "- Strictly scope-bounded"
    ]
    svg.append(f'  <rect x="1260" y="140" width="300" height="90" rx="6" fill="#b4befe" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(1260, 140, 300, 90)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_agent, 1275, 185, line_height=16, is_title=False, text_anchor="start")
    
    raw_agent = "\n".join(lines_agent)
    excalidraw_elements.extend(make_excalidraw_rect("agent_briefing", raw_agent, 1410, 185, 300, 90, "#b4befe", textAlign="left"))
    
    # Policy Sandbox
    lines_policy = [
        "Policy-Gated Replay Engine",
        "- Safe-read GET replays allowed",
        "- Approved staging writes only",
        "- Tenant boundary probes validated"
    ]
    svg.append(f'  <rect x="1260" y="245" width="300" height="90" rx="6" fill="#cba6f7" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(1260, 245, 300, 90)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_policy, 1275, 290, line_height=16, is_title=False, text_anchor="start")
    
    raw_policy = "\n".join(lines_policy)
    excalidraw_elements.extend(make_excalidraw_rect("policy_sandbox", raw_policy, 1410, 290, 300, 90, "#cba6f7", textAlign="left"))
    
    # Downstream Validation
    lines_validation = [
        "RedThread Dry-Run &amp; JudgeAgent",
        "- Confirms exploitability",
        "- Scores severity of confirmed bugs",
        "- Confirmed Findings + Remediation",
        "- Generates regression tests"
    ]
    svg.append(f'  <rect x="1260" y="350" width="300" height="100" rx="6" fill="#94e2d5" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(1260, 350, 300, 100)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_validation, 1275, 400, line_height=16, is_title=False, text_anchor="start")
    
    raw_validation = "\n".join(lines_validation).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("downstream_validation", raw_validation, 1410, 400, 300, 100, "#94e2d5", textAlign="left"))
    
    # Outputs box
    lines_out = [
        "Assurance Output Documents:",
        "- audit_trail.json &amp; confirmed_findings.json",
        "- remediation_queue.md"
    ]
    svg.append(f'  <rect x="1260" y="465" width="300" height="85" rx="6" fill="#89dceb" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(1260, 465, 300, 85)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_out, 1275, 507.5, line_height=18, is_title=False, text_anchor="start")
    
    raw_out = "\n".join(lines_out).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("assurance_outputs", raw_out, 1410, 507.5, 300, 85, "#89dceb", textAlign="left"))
    
    # ------------------ INTER-ZONE ARROWS ------------------
    # svg arrows
    svg.append(f'  <!-- Inter-zone flows -->')
    svg.append(f'  <path d="{sketchy_arrow(275, 225, 395, 170)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(340, 300, 395, 290)}" class="sketch-stroke-arrow" />')
    
    svg.append(f'  <!-- Zone 2 Internal flows -->')
    svg.append(f'  <path d="{sketchy_arrow(525, 170, 545, 170)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(675, 170, 695, 170)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(525, 290, 545, 290)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(675, 290, 695, 290)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(760, 205, 675, 270)}" class="sketch-stroke-arrow" />')
    svg.append(f'  <path d="{sketchy_arrow(610, 325, 610, 405)}" class="sketch-stroke-arrow" />')
    
    svg.append(f'  <!-- Zone 2 to Zone 3 flows -->')
    svg.append(f'  <path d="{sketchy_arrow(825, 170, 870, 170)}" class="sketch-stroke-arrow" style="stroke: #cba6f7;" />')
    svg.append(f'  <path d="{sketchy_arrow(825, 290, 870, 260)}" class="sketch-stroke-arrow" style="stroke: #cba6f7;" />')
    svg.append(f'  <path d="{sketchy_arrow(800, 445, 870, 465)}" class="sketch-stroke-arrow" style="stroke: #cba6f7;" />')
    
    svg.append(f'  <!-- Zone 3 to Zone 4 flows -->')
    svg.append(f'  <path d="{sketchy_arrow(1200, 200, 1260, 155)}" class="sketch-stroke-arrow" style="stroke: #89b4fa;" />')
    svg.append(f'  <path d="{sketchy_arrow(1200, 200, 1260, 255)}" class="sketch-stroke-arrow" style="stroke: #89b4fa;" />')
    svg.append(f'  <path d="{sketchy_arrow(1200, 465, 1260, 365)}" class="sketch-stroke-arrow" style="stroke: #fab387;" />')
    svg.append(f'  <path d="{sketchy_arrow(1200, 495, 1260, 480)}" class="sketch-stroke-arrow" style="stroke: #fab387;" />')
    
    # excalidraw arrows
    excalidraw_elements.append(make_excalidraw_arrow("zone1_to_zone2_act", 275, 225, 395, 170))
    excalidraw_elements.append(make_excalidraw_arrow("zone1_to_zone2_adp", 340, 300, 395, 290))
    
    excalidraw_elements.append(make_excalidraw_arrow("gate1_to_gate2", 525, 170, 545, 170))
    excalidraw_elements.append(make_excalidraw_arrow("gate2_to_gate3", 675, 170, 695, 170))
    excalidraw_elements.append(make_excalidraw_arrow("gate4_to_gate5", 525, 290, 545, 290))
    excalidraw_elements.append(make_excalidraw_arrow("gate5_to_gate6", 675, 290, 695, 290))
    excalidraw_elements.append(make_excalidraw_arrow("gate3_to_gate5", 760, 205, 675, 270))
    excalidraw_elements.append(make_excalidraw_arrow("gate5_to_code", 610, 325, 610, 405))
    
    excalidraw_elements.append(make_excalidraw_arrow("gate3_to_zone3", 825, 170, 870, 170))
    excalidraw_elements.append(make_excalidraw_arrow("gate6_to_zone3", 825, 290, 870, 260))
    excalidraw_elements.append(make_excalidraw_arrow("code_to_zone3", 800, 445, 870, 465))
    
    excalidraw_elements.append(make_excalidraw_arrow("zone3_to_zone4_agent", 1200, 200, 1260, 155))
    excalidraw_elements.append(make_excalidraw_arrow("zone3_to_zone4_replay", 1200, 200, 1260, 255))
    excalidraw_elements.append(make_excalidraw_arrow("zone3_to_zone4_dryrun", 1200, 465, 1260, 365))
    excalidraw_elements.append(make_excalidraw_arrow("zone3_to_zone4_outputs", 1200, 495, 1260, 480))
    
    # ------------------ CONTROLS TIMELINE ------------------
    # Title
    svg.append(f'  <text x="30" y="600" class="group-label">Controls: Ingestion Sanitization &amp; Gating</text>')
    excalidraw_elements.extend(make_excalidraw_boundary("controls_axis_label", "Controls: Ingestion Sanitization & Gating", 20, 580, 1560, 80))
    
    # Axis line
    svg.append(f'  <path d="{sketchy_line(40, 630, 1560, 630, overshoot=5, wobble=1.2)}" class="sketch-stroke" />')
    excalidraw_elements.append(make_excalidraw_line("axis_line", 40, 630, 1560, 630))
    
    # Markers (cx, cy, label)
    markers = [
        ("m1", "Ingest Sanitizer\n(filters noise)", 100, 630, "#cba6f7"),
        ("m2", "Privacy Audit\n(fails on secrets)", 300, 630, "#f38ba8"),
        ("m3", "Local Bridge Gate\n(approve/review/block)", 550, 630, "#fab387"),
        ("m4", "Staging Isolation\n(separate opt-in)", 800, 630, "#89b4fa"),
        ("m5", "Policy-Gated Replay\n(safe reads only)", 1050, 630, "#cba6f7"),
        ("m6", "JudgeAgent Confirm\n(downstream validation)", 1300, 630, "#94e2d5"),
        ("m7", "Regression Tests\n(incident protection)", 1500, 630, "#a6e3a1")
    ]
    for mid, text, mcx, mcy, mcolor in markers:
        # SVG circle and text
        svg.append(f'  <circle cx="{mcx}" cy="{mcy}" r="8" fill="{mcolor}" stroke="#ffffff" stroke-width="1.8" />')
        lines_marker = text.split("\n")
        draw_svg_text(svg, lines_marker, mcx, mcy + 25, line_height=14, is_title=False)
        
        # Excalidraw circle & text
        excalidraw_elements.extend(make_excalidraw_circle_marker(mid, text, mcx, mcy, 16, mcolor))
        
    # ------------------ BOTTOM GRIDS: THREATS & COLD REVIEW ------------------
    # 1. Threat Scenarios Boundary
    svg.append(f'  <rect x="20" y="680" width="800" height="230" rx="8" fill="#f38ba8" class="sketch-fill" />')
    boundary_threats_path = sketchy_rect(20, 680, 800, 230, overshoot=5, wobble=1.8)
    svg.append(f'  <path d="{boundary_threats_path}" class="sketch-stroke-arrow" stroke-dasharray="5,5" style="opacity: 0.5;" />')
    svg.append(f'  <text x="35" y="705" class="group-label">Red-team scenarios the MVP must fail closed / prevent</text>')
    excalidraw_elements.extend(make_excalidraw_boundary("boundary_threats", "Red-team scenarios the MVP must fail closed / prevent", 20, 680, 800, 230))
    
    # 4 Red-Team Boxes
    threat_boxes = [
        ("threat1", [
            "Prompt Secret Leak",
            "LLM prompt receives raw",
            "cookies / session tokens.",
            "",
            "Prevention:",
            "Privacy Audit fails closed",
            "before prompt generation."
        ], 125, 805, 170, 160),
        ("threat2", [
            "Cross-Tenant Access",
            "Agent attempts to read /",
            "write neighboring tenant IDs.",
            "",
            "Prevention:",
            "Tenant boundary probes",
            "block unmapped IDs."
        ], 315, 805, 170, 160),
        ("threat3", [
            "Destructive Action",
            "Agent triggers deleting /",
            "destructive API execution.",
            "",
            "Prevention:",
            "Blocked Destructive policy",
            "denies by default."
        ], 505, 805, 170, 160),
        ("threat4", [
            "Unapproved Write",
            "Mutating POST replayed",
            "without staging auth.",
            "",
            "Prevention:",
            "Writes blocked unless",
            "staging auth bundle exists."
        ], 695, 805, 170, 160)
    ]
    for tid, lines, tcx, tcy, tw, th in threat_boxes:
        svg.append(f'  <rect x="{tcx - tw/2}" y="{tcy - th/2}" width="{tw}" height="{th}" rx="6" fill="#ffd1d1" class="sketch-fill" />')
        threat_path = sketchy_rect(tcx - tw/2, tcy - th/2, tw, th)
        svg.append(f'  <path d="{threat_path}" class="sketch-stroke" style="stroke: #f38ba8; stroke-width: 2;" />')
        draw_svg_text(svg, lines, tcx, tcy, line_height=14, is_title=False)
        
        raw_text = "\n".join(lines)
        excalidraw_elements.extend(make_excalidraw_rect(tid, raw_text, tcx, tcy, tw, th, "#ffd1d1"))
        
    # 2. Cold Review Checklist Boundary
    svg.append(f'  <rect x="850" y="680" width="730" height="230" rx="8" fill="#f9e2af" class="sketch-fill" />')
    boundary_checklist_path = sketchy_rect(850, 680, 730, 230, overshoot=5, wobble=1.8)
    svg.append(f'  <path d="{boundary_checklist_path}" class="sketch-stroke-arrow" stroke-dasharray="5,5" style="opacity: 0.5;" />')
    svg.append(f'  <text x="865" y="705" class="group-label">Human Validation &amp; Verification Questions (Cold Review Protocol)</text>')
    excalidraw_elements.extend(make_excalidraw_boundary("boundary_checklist", "Human Validation & Verification Questions (Cold Review Protocol)", 850, 680, 730, 230))
    
    # Checklist Big Box
    lines_checklist = [
        "Cold-Review &amp; Distribution Protocol Checklist:",
        "1. Has the reviewer validated that no raw PII or tokens are present in reviewer_packet.md?",
        "2. Are all action catalogs classified as read vs write with proper destructive potential?",
        "3. Are the allowed environments pinned to non-production staging/test hosts only?",
        "4. Has a multi-reviewer distribution manifest been signed off by the lead AI security engineer?",
        "5. Are target boundaries and user/tenant scopes explicitly documented and verified?"
    ]
    svg.append(f'  <rect x="870" y="725" width="690" height="160" rx="6" fill="#fef2d1" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(870, 725, 690, 160)}" class="sketch-stroke" style="stroke: #f9e2af; stroke-width: 2;" />')
    draw_svg_text(svg, lines_checklist, 885, 805, line_height=20, is_title=False, text_anchor="start")
    
    raw_checklist = "\n".join(lines_checklist).replace("&amp;", "&")
    excalidraw_elements.extend(make_excalidraw_rect("checklist_box", raw_checklist, 1215, 805, 690, 160, "#fef2d1", textAlign="left"))
    
    # ------------------ STATUS NOTE / ENGINE NOTE BANNER ------------------
    svg.append(f'  <rect x="20" y="930" width="1560" height="70" rx="8" fill="#89dceb" class="sketch-fill" />')
    boundary_banner_path = sketchy_rect(20, 930, 1560, 70, overshoot=6, wobble=1.5)
    svg.append(f'  <path d="{boundary_banner_path}" class="sketch-stroke-arrow" stroke-dasharray="5,5" style="opacity: 0.5;" />')
    svg.append(f'  <text x="35" y="950" class="group-label">Integration Architecture &amp; Current Status</text>')
    excalidraw_elements.extend(make_excalidraw_boundary("boundary_banner", "Integration Architecture & Current Status", 20, 930, 1560, 70))
    
    lines_banner = [
        "adopt-redthread is a fully operational Context Bridge (v0 spec) and Approved Context Replay v1 engine.",
        "Replay evaluation uses the sibling RedThread virtualenv by default. Primary focus is making the reviewer-facing evidence path unmistakably clear.",
        "Confirmatory exploitation, confirmed findings, and severity scoring are strictly deferred downstream to RedThread."
    ]
    svg.append(f'  <rect x="35" y="955" width="1530" height="38" rx="4" fill="#cbe3f7" class="sketch-fill" />')
    svg.append(f'  <path d="{sketchy_rect(35, 955, 1530, 38)}" class="sketch-stroke" />')
    draw_svg_text(svg, lines_banner, 800, 974, line_height=11, is_title=False)
    
    raw_banner = "\n".join(lines_banner)
    excalidraw_elements.extend(make_excalidraw_rect("banner_box", raw_banner, 800, 974, 1530, 38, "#cbe3f7"))
    
    svg.append('</svg>')
    
    output_dir = "/Users/matheusvsky/Documents/personal/adopt-redthread/docs/assets"
    os.makedirs(output_dir, exist_ok=True)
    
    tmp_svg_path = os.path.join(output_dir, "architecture.tmp.svg")
    with open(tmp_svg_path, "w") as f:
        f.write("\n".join(svg))
        
    excalidraw_path = os.path.join(output_dir, "architecture.excalidraw")
    save_excalidraw_file(excalidraw_elements, excalidraw_path)
    
    return tmp_svg_path, os.path.join(output_dir, "architecture.png")

def create_flow_diagram():
    svg_width = 1000
    svg_height = 750
    
    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="100%" height="100%" style="background: transparent;">')
    svg.append("""  <defs>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Architects+Daughter&amp;family=Comic+Neue:wght@400;700&amp;display=swap');
      
      .label-title {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 13px;
        font-weight: bold;
        fill: #ffffff;
      }
      
      .label-text {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 11px;
        fill: #ffffff;
      }
      
      .sketch-stroke {
        stroke: #ffffff;
        stroke-width: 1.8;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.85;
      }
      
      .sketch-stroke-arrow {
        stroke: #ffffff;
        stroke-width: 1.5;
        fill: none;
        stroke-linecap: round;
        stroke-linejoin: round;
        opacity: 0.75;
      }
      
      .sketch-fill {
        stroke: none;
        opacity: 0.12;
      }
      
      .group-label {
        font-family: 'Architects Daughter', 'Comic Neue', 'Comic Sans MS', sans-serif;
        font-size: 14px;
        font-weight: bold;
        fill: #ffffff;
      }
    </style>
  </defs>""")
    
    excalidraw_elements = []
    
    # Outer flow boundary
    svg.append(f'  <rect x="10" y="10" width="980" height="730" rx="8" fill="#b4befe" class="sketch-fill" />')
    outer_path = sketchy_rect(10, 10, 980, 730, overshoot=5, wobble=1.8)
    svg.append(f'  <path d="{outer_path}" class="sketch-stroke-arrow" stroke-dasharray="6,6" style="opacity: 0.4;" />')
    svg.append(f'  <text x="25" y="30" class="group-label">adopt-redthread E2E Context &amp; Evidence Flow</text>')
    
    excalidraw_elements.extend(make_excalidraw_boundary("flow_boundary", "adopt-redthread E2E Context & Evidence Flow", 10, 10, 980, 730))
    
    # Flow Nodes
    nodes = [
        ("flow1", ["Real App or Website"], 500, 60, 200, 45, "#89b4fa"),
        ("flow2", ["Discovery Intake Lanes", "(HAR, ZAPI, NoUI, Adopt)"], 500, 135, 400, 50, "#cba6f7"),
        ("flow3", ["Bridge Sanitizer &amp; Privacy Audit"], 500, 215, 340, 50, "#f38ba8"),
        ("flow4", ["Normalized Fixtures &amp; Workflow Plans"], 500, 295, 380, 50, "#fab387"),
        
        ("flow5_left", ["Bridge-Owned Live /", "Workflow Replay Evidence"], 260, 385, 320, 60, "#f5c2e7"),
        ("flow5_right", ["RedThread Runtime Inputs"], 740, 385, 260, 50, "#89dceb"),
        
        ("flow6", ["RedThread Replay Verdict", "&amp; Dry-Run Evidence"], 740, 475, 320, 60, "#f9e2af"),
        
        ("flow7", ["Local Bridge Pre-Publish Gate"], 500, 580, 380, 55, "#b4befe"),
        ("flow8", ["Decision: Approve / Review / Block"], 500, 670, 320, 50, "#a6e3a1")
    ]
    
    for nid, lines, cx, cy, w, h, color in nodes:
        x = cx - w/2
        y = cy - h/2
        svg.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{color}" class="sketch-fill" />')
        border_path = sketchy_rect(x, y, w, h)
        svg.append(f'  <path d="{border_path}" class="sketch-stroke" />')
        
        draw_svg_text(svg, lines, cx, cy, is_title=True)
        
        raw_text = "\n".join(lines).replace("&amp;", "&")
        excalidraw_elements.extend(make_excalidraw_rect(nid, raw_text, cx, cy, w, h, color))
        
    # Flow Arrows
    arrows = [
        ("f_a1", 500, 82.5, 500, 110),
        ("f_a2", 500, 160, 500, 190),
        ("f_a3", 500, 240, 500, 270),
        
        ("f_a4_l", 500, 320, 260, 355),
        ("f_a4_r", 500, 320, 740, 360),
        
        ("f_a5_r", 740, 410, 740, 445),
        
        ("f_a6_l", 260, 415, 500, 552.5),
        ("f_a6_r", 740, 505, 500, 552.5),
        
        ("f_a7", 500, 607.5, 500, 645)
    ]
    
    for aid, x1, y1, x2, y2 in arrows:
        svg.append(f'  <path d="{sketchy_arrow(x1, y1, x2, y2)}" class="sketch-stroke-arrow" />')
        excalidraw_elements.append(make_excalidraw_arrow(aid, x1, y1, x2, y2))
        
    svg.append('</svg>')
    
    output_dir = "/Users/matheusvsky/Documents/personal/adopt-redthread/docs/assets"
    
    tmp_svg_path = os.path.join(output_dir, "high_level_flow.tmp.svg")
    with open(tmp_svg_path, "w") as f:
        f.write("\n".join(svg))
        
    excalidraw_path = os.path.join(output_dir, "high_level_flow.excalidraw")
    save_excalidraw_file(excalidraw_elements, excalidraw_path)
    
    return tmp_svg_path, os.path.join(output_dir, "high_level_flow.png")

# ------------------ CONVERSION AND CLEANUP ------------------
def convert_svg_to_png(svg_path, png_path, width):
    print(f"Converting {svg_path} to PNG at {png_path} (width: {width})...")
    cmd = [
        "npx", "-y", "@resvg/resvg-js-cli",
        "--fit-width", str(width),
        svg_path, png_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Generated PNG: {png_path}")
    
    # Clean up temporary SVG
    if os.path.exists(svg_path):
        os.remove(svg_path)
        print(f"Cleaned up temporary SVG: {svg_path}")

def clean_old_svgs():
    output_dir = "/Users/matheusvsky/Documents/personal/adopt-redthread/docs/assets"
    for filename in ["architecture.svg", "high_level_flow.svg"]:
        path = os.path.join(output_dir, filename)
        if os.path.exists(path):
            os.remove(path)
            print(f"Deleted old SVG: {path}")

if __name__ == "__main__":
    clean_old_svgs()
    
    # Generate and convert architecture diagram (High res 3200 for extremely crisp details!)
    tmp_svg_arch, png_arch = create_architecture_diagram()
    convert_svg_to_png(tmp_svg_arch, png_arch, 3200)
    
    # Generate and convert high level flow
    tmp_svg_flow, png_flow = create_flow_diagram()
    convert_svg_to_png(tmp_svg_flow, png_flow, 2000)
    
    print("\n--- ALL PREMIUM DIAGRAMS SUCCESSFULLY GENERATED ---")
