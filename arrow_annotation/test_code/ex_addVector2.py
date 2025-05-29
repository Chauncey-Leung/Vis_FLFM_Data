import napari
import tifffile
import numpy as np
import json, os
from qtpy.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QMenu
)

# === 文件与图层初始化 ===
default_tiff = 'recon_ss_single_0007.tiff'
default_path = os.path.dirname(os.path.abspath(default_tiff))
default_json_path = os.path.join(default_path, 'saved_vectors.json')

volume = tifffile.imread(default_tiff)
viewer = napari.Viewer(ndisplay=3)
image_layer = viewer.add_image(volume, colormap='green', scale=(5, 0.91, 0.91), rendering='mip')

vectors_layer = viewer.add_vectors(np.empty((0, 2, 3)),
                                   edge_color='red',
                                   vector_style='arrow',
                                   name="Arrow_vector",
                                   edge_width=3,
                                   length=1.0,
                                   opacity=1.0)

# === 表格初始化 ===
table = QTableWidget()
table.setColumnCount(7)
table.setHorizontalHeaderLabels(['Start (Z,Y,X)', 'Direction (dZ,dY,dX)', 'Color', 'Width', 'Length', 'Style', 'Index'])

path_input = QLineEdit()
path_input.setPlaceholderText("保存/加载路径")
path_input.setText(default_json_path)

# === 矢量数据同步 ===
is_updating_table = False
def refresh_vector_table():
    global is_updating_table
    is_updating_table = True
    try:
        table.blockSignals(True)
        data = vectors_layer.data
        table.setRowCount(len(data))
        for i, vec in enumerate(data):
            start = vec[0]
            direction = vec[1]
            table.setItem(i, 0, QTableWidgetItem(np.array2string(start, precision=2)))
            table.setItem(i, 1, QTableWidgetItem(np.array2string(direction, precision=2)))
            table.setItem(i, 2, QTableWidgetItem(str(vectors_layer.edge_color)))
            table.setItem(i, 3, QTableWidgetItem(str(vectors_layer.edge_width)))
            table.setItem(i, 4, QTableWidgetItem(str(vectors_layer.length)))
            table.setItem(i, 5, QTableWidgetItem(vectors_layer.vector_style))
            table.setItem(i, 6, QTableWidgetItem(str(i)))
    finally:
        table.blockSignals(False)
        is_updating_table = False

def update_vector_from_table(row):
    try:
        start = np.fromstring(table.item(row, 0).text().strip("[]"), sep=' ')
        direction = np.fromstring(table.item(row, 1).text().strip("[]"), sep=' ')
        color = table.item(row, 2).text().strip()
        width = float(table.item(row, 3).text().strip())
        length = float(table.item(row, 4).text().strip())
        style = table.item(row, 5).text().strip()

        new_data = vectors_layer.data.copy()
        new_data[row] = [start, direction]
        vectors_layer.data = new_data
        vectors_layer.edge_color = color
        vectors_layer.edge_width = width
        vectors_layer.length = length
        vectors_layer.vector_style = style
    except Exception as e:
        print(f"更新第 {row} 行时发生错误：{e}")

def on_table_item_changed(item):
    if is_updating_table:
        return
    update_vector_from_table(item.row())
table.itemChanged.connect(on_table_item_changed)

# === 添加/保存/加载功能 ===
def save_vectors_to_file():
    if len(vectors_layer.data) == 0:
        print("No vectors to save.")
        return

    vector_data = []
    for vec in vectors_layer.data:
        start = vec[0]
        direction = vec[1]
        vector_data.append({
            'start': start.tolist(),
            'direction': direction.tolist(),
            'edge_color': vectors_layer.edge_color,
            'edge_width': vectors_layer.edge_width,
            'length': vectors_layer.length,
            'vector_style': vectors_layer.vector_style,
        })

    save_path = path_input.text().strip() or default_json_path
    with open(save_path, 'w') as f:
        json.dump(vector_data, f, indent=2)
    print(f"Saved {len(vector_data)} vectors to '{save_path}'")

def load_vectors_from_file():
    load_path = path_input.text().strip() or default_json_path
    if not os.path.exists(load_path):
        print(f"File '{load_path}' not found.")
        return

    with open(load_path, 'r') as f:
        vector_data = json.load(f)

    vectors = []
    for vec in vector_data:
        start = np.array(vec['start'])
        direction = np.array(vec['direction'])
        vectors.append([start, direction])

    vectors_layer.data = np.array(vectors)
    vectors_layer.edge_color = vector_data[0].get('edge_color', 'red')
    vectors_layer.edge_width = vector_data[0].get('edge_width', 2)
    vectors_layer.length = vector_data[0].get('length', 1)
    vectors_layer.vector_style = vector_data[0].get('vector_style', 'arrow')
    refresh_vector_table()
    print(f"Loaded {len(vectors)} vectors from '{load_path}'")

def clear_vectors():
    vectors_layer.data = np.empty((0, 2, 3))
    refresh_vector_table()
    print("Vectors cleared.")

# === 相机射线相关函数 ===
ray_info = {'first': None, 'second': None}

def get_camera_ray(event):
    view = viewer.window.qt_viewer.view
    canvas_transform = view.scene.transform
    pos_canvas = np.array(event.pos)
    p_near = np.array([*pos_canvas, 0, 1])
    p_far = np.array([*pos_canvas, 1, 1])
    world_near = canvas_transform.imap(p_near)[:3]
    world_far = canvas_transform.imap(p_far)[:3]
    direction = world_far - world_near
    direction /= np.linalg.norm(direction)
    return world_near, direction

def triangulate_rays(p1, d1, p2, d2):
    w0 = p1 - p2
    a = np.dot(d1, d1)
    b = np.dot(d1, d2)
    c = np.dot(d2, d2)
    d = np.dot(d1, w0)
    e = np.dot(d2, w0)
    denom = a * c - b * b
    if np.isclose(denom, 0):
        return None
    t = (b * e - c * d) / denom
    s = (a * e - b * d) / denom
    return (p1 + t * d1 + p2 + s * d2) / 2

def draw_vector(target_point, direction, length_scale=25):
    unit_direction = direction / np.linalg.norm(direction)
    start_point = target_point - unit_direction * length_scale
    vector = np.array([[start_point, unit_direction * length_scale]])
    vectors_layer.data = np.concatenate([vectors_layer.data, vector], axis=0)
    refresh_vector_table()

def handle_right_click(layer, event):
    if event.button != 2:
        return
    pos, direction = get_camera_ray(event)
    menu = QMenu()
    act1 = menu.addAction("First Click")
    act2 = menu.addAction("Second Click")
    action = menu.exec_(event.native.globalPos())
    if action == act1:
        ray_info['first'] = (pos, direction)
        print("First click recorded.")
    elif action == act2:
        ray_info['second'] = (pos, direction)
        print("Second click recorded.")

    if ray_info['first'] and ray_info['second']:
        p1, d1 = ray_info['first']
        p2, d2 = ray_info['second']
        mid = triangulate_rays(p1, d1, p2, d2)
        if mid is not None:
            mid_zyx = mid[[2, 1, 0]]
            draw_vector(mid_zyx, np.array([0, 1, 1]))  # 方向可换
        else:
            print("Triangulation failed.")
        ray_info['first'] = None
        ray_info['second'] = None

# === UI 布局 ===
save_button = QPushButton("Save Vectors")
load_button = QPushButton("Load Vectors")
clear_button = QPushButton("Clear Vectors")
save_button.clicked.connect(save_vectors_to_file)
load_button.clicked.connect(load_vectors_from_file)
clear_button.clicked.connect(clear_vectors)

controls = QWidget()
layout = QVBoxLayout()
layout.addWidget(path_input)
layout.addWidget(save_button)
layout.addWidget(load_button)
layout.addWidget(clear_button)
layout.addWidget(table)
controls.setLayout(layout)
viewer.window.add_dock_widget(controls, area='right')

# === 绑定事件 ===
image_layer.mouse_double_click_callbacks.append(handle_right_click)

napari.run()
