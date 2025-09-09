import math
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Polygon, Circle
import os

def generate_fear_greed_chart(data):
    """
    Generates the Fear & Greed Index gauge chart and saves it as a PNG image.
    The data structure is expected to be similar to the example provided by the user.
    """
    # ===== JSONデータ例 =====
    # data = {
    #     "center_value": 52,
    #     "history": {
    #         "previous_close": {"label": "Previous close", "status": "Neutral", "value": 53},
    #         "week_ago": {"label": "1 week ago", "status": "Greed", "value": 60},
    #         "month_ago": {"label": "1 month ago", "status": "Greed", "value": 58},
    #         "year_ago": {"label": "1 year ago", "status": "Fear", "value": 39}
    #     }
    # }

    # Define the output path for the image
    # The script is in backend/, so we go up one level to the project root, then to frontend/
    output_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'fear_and_greed_gauge.png')

    # ステータスごとの色設定
    status_colors = {
        "Fear": ("#f6a35c", "#cc6600"),     # 背景, 枠
        "Neutral": ("#bfbfbf", "#666666"),
        "Greed": ("#66cc99", "#006633"),
        "Extreme Fear": ("#f6a35c", "#cc6600"), # Added for completeness
        "Extreme Greed": ("#66cc99", "#006633") # Added for completeness
    }

    # ===== ゲージ描画 =====
    value = data["center_value"]
    labels = ["EXTREME FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME GREED"]
    n = len(labels)
    start_angle = 180
    end_angle = 0
    radius_outer = 1.0
    radius_inner = 0.6

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={'aspect':'equal'}) # 少し縦長に調整
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.3, 1.5) # 下部の表示エリアを確保
    ax.axis('off')

    angle_span = (start_angle - end_angle) / n
    for i, label in enumerate(labels):
        a1 = start_angle - i * angle_span
        a2 = a1 - angle_span
        # 現在の値がどのセグメントにあるか判定
        current_segment_index = math.floor((value / 100) * n)
        if current_segment_index == 5: current_segment_index = 4 # 100の場合のインデックス調整

        if i == current_segment_index:
            face = '#e0e0e0' # 元画像のグレーを再現
            edge = 'black'
            lw = 1.5
        else:
            face = '#f0f0f0' # 元画像の白に近い色を再現
            edge = '#d3d3d3' # 薄いグレーの境界線
            lw = 1.0
        wedge = Wedge((0,0), radius_outer, a2, a1, width=radius_outer-radius_inner,
                      facecolor=face, edgecolor=edge, linewidth=lw, zorder=1)
        ax.add_patch(wedge)
        mid_angle = math.radians((a1+a2)/2)
        lx = (radius_outer + 0.15) * math.cos(mid_angle)
        ly = (radius_outer + 0.15) * math.sin(mid_angle)
        ax.text(lx, ly, label, ha='center', va='center', fontsize=11, fontweight='bold', color='#555555')

    # 目盛り（数字と点、5刻み）
    for pct in range(0, 101, 5):
        ang = math.radians(start_angle - (pct/100)*(start_angle-end_angle))
        r_text = radius_inner - 0.1
        x_text = r_text * math.cos(ang)
        y_text = r_text * math.sin(ang)
        if pct % 25 == 0:
            ax.text(x_text, y_text, str(pct), ha='center', va='center', fontsize=9, color='#333333')
        else:
            ax.plot([x_text], [y_text], marker='.', markersize=4, color='grey', zorder=2)

    # 針
    needle_angle = math.radians(start_angle - (value/100)*(start_angle-end_angle))
    needle_length = radius_outer - 0.05
    w = 0.02
    dx = w * math.cos(needle_angle + math.pi/2)
    dy = w * math.sin(needle_angle + math.pi/2)
    x_tip = needle_length * math.cos(needle_angle)
    y_tip = needle_length * math.sin(needle_angle)
    poly_coords = [(-dx, -dy*2), (x_tip, y_tip), (dx, -dy*2)] # 三角形に形状変更
    needle = Polygon(poly_coords, closed=True, facecolor='black', edgecolor='black', zorder=4)
    ax.add_patch(needle)

    # 中央の数字
    center_pivot = Circle((0,0), 0.15, facecolor='white', edgecolor='black', linewidth=0.5, zorder=5)
    ax.add_patch(center_pivot)
    ax.text(0, 0, str(value), fontsize=32, fontweight='bold', ha='center', va='center', zorder=6)

    # ===== 下部情報エリア (縦一列に修正) =====
    history = data["history"]
    history_keys = ["previous_close", "week_ago", "month_ago", "year_ago"]

    # 配置の初期設定
    start_y = -0.25
    y_step = -0.2
    x_label = -1.4
    x_status = 0.0
    x_circle = 1.0

    for i, key in enumerate(history_keys):
        if key not in history:
            continue
        item = history[key]
        label = item["label"]
        status = item["status"]
        val = item["value"]
        bg, border = status_colors.get(status, ("#cccccc", "#666666"))

        current_y = start_y + i * y_step

        # テキスト（ラベル）
        ax.text(x_label, current_y, label, ha='left', va='center', fontsize=10, color='grey')
        # テキスト（状態）
        ax.text(x_status, current_y, status, ha='left', va='center', fontsize=10, fontweight='bold')

        # 数字が入る円
        circle = Circle((x_circle, current_y), 0.1, facecolor=bg, edgecolor=border, linewidth=1.0, zorder=3)
        ax.add_patch(circle)
        ax.text(x_circle, current_y, str(val), ha='center', va='center', fontsize=10, fontweight='bold', color='white')

        # 区切り線 (最後の項目以外)
        if i < len(history_keys) - 1:
            line_y = current_y + y_step / 2
            ax.plot([x_label, x_circle + 0.3], [line_y, line_y], color='#e0e0e0', linestyle='dotted', linewidth=1)

    plt.savefig(output_path, bbox_inches='tight', pad_inches=0.1)
    plt.close(fig) # Close the figure to free up memory
