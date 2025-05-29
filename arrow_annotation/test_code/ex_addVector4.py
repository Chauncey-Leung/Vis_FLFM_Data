import napari
import tifffile
import numpy as np
import json, os
from qtpy.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QComboBox, QMenu
)

# === 初始化 ===
default_tiff = 'recon_ss_single_0007.tiff'
default_path = os.path.dirname(os.path.abspath(default_tiff))
default_json_path = os.path.join(default_path, 'saved_vectors.json')
available_colors = [
    'red', 'green', 'blue', 'yellow', 'cyan', 'magenta',
    'orange', 'purple', 'lime', 'pink', 'brown', 'gray', 'black',
    'navy', 'teal', 'gold', 'salmon', 'indigo', 'olive', 'maroon'
]

volume = tifffile.imread(default_tiff)
viewer = napari.Viewer(ndisplay=3)
image_layer = viewer.add_image(volume, colormap='green', scale=(5, 0.91, 0.91), rendering='mip')

# === 控件 ===
table = QTableWidget()
table.setColumnCount(6)
table.setHorizontalHeaderLabels(['Start (Z,Y,X)', 'Direction (dZ,dY,dX)', 'Color', 'Width', 'Length', 'Delete'])
path_input = QLineEdit()
path_input.setText(default_json_path)

# === 全局状态 ===
is_updating_table = False
ray_info = {'first': None, 'second': None}
vector_layers = []
color_boxes = []
color_values = []  # store per-arrow color

# === 函数定义 ===
def refresh_vector_table():
    global is_updating_table, color_boxes
    is_updating_table = True
    color_boxes = []
    try:
        table.blockSignals(True)
        table.setRowCount(len(vector_layers))
        for i, vec_layer in enumerate(vector_layers):
            vec = vec_layer.data[0]
            start, direction = vec
            table.setItem(i, 0, QTableWidgetItem(np.array2string(start, precision=2)))
            table.setItem(i, 1, QTableWidgetItem(np.array2string(direction, precision=2)))

            color_box = QComboBox()
            color_box.addItems(available_colors)
            color = color_values[i] if i < len(color_values) else vec_layer.edge_color
            color_box.setCurrentText(color)
            color_box.currentTextChanged.connect(lambda _, row=i: update_color_from_table(row))
            table.setCellWidget(i, 2, color_box)
            color_boxes.append(color_box)

            table.setItem(i, 3, QTableWidgetItem(str(vec_layer.edge_width)))
            table.setItem(i, 4, QTableWidgetItem(str(vec_layer.length)))

            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda _, row=i: delete_vector(row))
            table.setCellWidget(i, 5, del_btn)
    finally:
        table.blockSignals(False)
        is_updating_table = False

def update_color_from_table(row):
    vec_layer = vector_layers[row]
    color_box = color_boxes[row]
    color = color_box.currentText()
    vec_layer.edge_color = color
    if row < len(color_values):
        color_values[row] = color
    else:
        color_values.append(color)

def update_vector_from_table(row):
    vec_layer = vector_layers[row]
    start = np.fromstring(table.item(row, 0).text().strip("[]"), sep=' ')
    direction = np.fromstring(table.item(row, 1).text().strip("[]"), sep=' ')
    width = float(table.item(row, 3).text().strip())
    length = float(table.item(row, 4).text().strip())
    vec_layer.data = np.array([[start, direction]])
    vec_layer.edge_width = width
    vec_layer.length = length

def on_table_item_changed(item):
    if is_updating_table:
        return
    update_vector_from_table(item.row())

table.itemChanged.connect(on_table_item_changed)

def delete_vector(row):
    vec_layer = vector_layers.pop(row)
    viewer.layers.remove(vec_layer)
    if row < len(color_values):
        color_values.pop(row)
    refresh_vector_table()

def save_vectors_to_file():
    data = []
    for i, vec_layer in enumerate(vector_layers):
        vec = vec_layer.data[0]
        start, direction = vec
        color = color_values[i] if i < len(color_values) else vec_layer.edge_color
        data.append({
            'start': start.tolist(),
            'direction': direction.tolist(),
            'edge_color': color,
            'edge_width': vec_layer.edge_width,
            'length': vec_layer.length
        })
    with open(path_input.text(), 'w') as f:
        json.dump(data, f, indent=2)

def load_vectors_from_file():
    clear_vectors()
    with open(path_input.text(), 'r') as f:
        data = json.load(f)
    for item in data:
        draw_vector(
            point=np.array(item['start']),
            direction=np.array(item['direction']),
            length=item.get('length', 1.0),
            color=item.get('edge_color', 'red'),
            width=item.get('edge_width', 3),
            refresh=False
        )
    refresh_vector_table()

def clear_vectors():
    for vec_layer in vector_layers:
        viewer.layers.remove(vec_layer)
    vector_layers.clear()
    color_values.clear()
    refresh_vector_table()

def get_camera_ray(event):
    view = viewer.window.qt_viewer.view
    transform = view.scene.transform
    pos = np.array(event.pos)
    p_near = np.array([*pos, 0, 1])
    p_far = np.array([*pos, 1, 1])
    near = transform.imap(p_near)[:3]
    far = transform.imap(p_far)[:3]
    dir = far - near
    return near, dir / np.linalg.norm(dir)

def triangulate_rays(p1, d1, p2, d2):
    w0 = p1 - p2
    a, b, c = np.dot(d1, d1), np.dot(d1, d2), np.dot(d2, d2)
    d, e = np.dot(d1, w0), np.dot(d2, w0)
    denom = a * c - b * b
    if np.isclose(denom, 0): return None
    t, s = (b * e - c * d) / denom, (a * e - b * d) / denom
    return (p1 + t * d1 + p2 + s * d2) / 2

def draw_vector(point, direction, length=25, color='red', width=3, refresh=True):
    unit = direction / np.linalg.norm(direction)
    start = point - unit * length
    data = np.array([[start, unit * length]])
    vec_layer = viewer.add_vectors(
        data,
        edge_width=width,
        length=1.0,
        vector_style='arrow',
        edge_color=color,
        name=f"arrow_{len(vector_layers)}"
    )
    vector_layers.append(vec_layer)
    color_values.append(color)
    viewer.layers.selection.clear()
    viewer.layers.selection.add(image_layer)
    if refresh:
        refresh_vector_table()

def handle_right_click(layer, event):
    if event.button != 2: return
    pos, direction = get_camera_ray(event)
    menu = QMenu()
    act1 = menu.addAction("First Click")
    act2 = menu.addAction("Second Click")
    action = menu.exec_(event.native.globalPos())
    if action == act1:
        ray_info['first'] = (pos, direction)
    elif action == act2:
        ray_info['second'] = (pos, direction)

    if ray_info['first'] and ray_info['second']:
        p1, d1 = ray_info['first']
        p2, d2 = ray_info['second']
        mid = triangulate_rays(p1, d1, p2, d2)
        if mid is not None:
            draw_vector(mid[[2,1,0]], np.array([0,1,1]), length=25, color='red', width=3)
        ray_info['first'] = ray_info['second'] = None

# === UI 布局 ===
save_btn = QPushButton("Save Vectors")
load_btn = QPushButton("Load Vectors")
clear_btn = QPushButton("Clear Vectors")
save_btn.clicked.connect(save_vectors_to_file)
load_btn.clicked.connect(load_vectors_from_file)
clear_btn.clicked.connect(clear_vectors)

controls = QWidget()
layout = QVBoxLayout()
layout.addWidget(path_input)
layout.addWidget(save_btn)
layout.addWidget(load_btn)
layout.addWidget(clear_btn)
layout.addWidget(table)
controls.setLayout(layout)
viewer.window.add_dock_widget(controls, area='right')

image_layer.mouse_double_click_callbacks.append(handle_right_click)
napari.run()
