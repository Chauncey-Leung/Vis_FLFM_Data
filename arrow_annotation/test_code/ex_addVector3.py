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
available_colors = ['red', 'green', 'blue', 'yellow', 'cyan', 'magenta']

volume = tifffile.imread(default_tiff)
viewer = napari.Viewer(ndisplay=3)
image_layer = viewer.add_image(volume, colormap='green', scale=(5, 0.91, 0.91), rendering='mip')

vectors_layer = viewer.add_vectors(
    np.empty((0, 2, 3)),
    edge_width=3,
    length=1.0,
    vector_style='arrow',
    name="Arrow_vector"
)

# === 控件 ===
table = QTableWidget()
table.setColumnCount(6)
table.setHorizontalHeaderLabels(['Start (Z,Y,X)', 'Direction (dZ,dY,dX)', 'Color', 'Width', 'Length', 'Delete'])
path_input = QLineEdit()
path_input.setText(default_json_path)

# === 全局状态 ===
is_updating_table = False
ray_info = {'first': None, 'second': None}
vector_widths = []
vector_lengths = []

# === 函数定义 ===
def refresh_vector_table():
    global is_updating_table
    is_updating_table = True
    try:
        table.blockSignals(True)
        table.setRowCount(len(vectors_layer.data))
        for i, vec in enumerate(vectors_layer.data):
            start, direction = vec
            table.setItem(i, 0, QTableWidgetItem(np.array2string(start, precision=2)))
            table.setItem(i, 1, QTableWidgetItem(np.array2string(direction, precision=2)))

            color_box = QComboBox()
            color_box.addItems(available_colors)
            if 'color' in vectors_layer.properties:
                color_box.setCurrentText(str(vectors_layer.properties['color'][i]))
            color_box.currentTextChanged.connect(lambda _, row=i: update_color_from_table(row))
            table.setCellWidget(i, 2, color_box)

            table.setItem(i, 3, QTableWidgetItem(str(vector_widths[i] if i < len(vector_widths) else 3)))
            table.setItem(i, 4, QTableWidgetItem(str(vector_lengths[i] if i < len(vector_lengths) else 1.0)))

            del_btn = QPushButton("Delete")
            del_btn.clicked.connect(lambda _, row=i: delete_vector(row))
            table.setCellWidget(i, 5, del_btn)
    finally:
        table.blockSignals(False)
        is_updating_table = False

def update_color_from_table(row):
    colors = []
    for i in range(table.rowCount()):
        box = table.cellWidget(i, 2)
        if isinstance(box, QComboBox):
            colors.append(box.currentText())
    vectors_layer.properties['color'] = colors
    vectors_layer.edge_color = 'color'
    vectors_layer.edge_color_mode = 'cycle'
    vectors_layer.properties = dict(vectors_layer.properties)

def update_vector_from_table(row):
    start = np.fromstring(table.item(row, 0).text().strip("[]"), sep=' ')
    direction = np.fromstring(table.item(row, 1).text().strip("[]"), sep=' ')
    width = float(table.item(row, 3).text().strip())
    length = float(table.item(row, 4).text().strip())

    new_data = vectors_layer.data.copy()
    new_data[row] = [start, direction]
    vectors_layer.data = new_data

    if row < len(vector_widths):
        vector_widths[row] = width
    else:
        vector_widths.append(width)

    if row < len(vector_lengths):
        vector_lengths[row] = length
    else:
        vector_lengths.append(length)

    vectors_layer.edge_width = width  # 可选：如果想让最后一个宽度应用到所有箭头
    vectors_layer.length = length     # 可选：如果想让最后一个长度应用到所有箭头

def on_table_item_changed(item):
    if is_updating_table:
        return
    update_vector_from_table(item.row())

table.itemChanged.connect(on_table_item_changed)

def delete_vector(row):
    vectors_layer.data = np.delete(vectors_layer.data, row, axis=0)
    if 'color' in vectors_layer.properties:
        colors = list(vectors_layer.properties['color'])
        del colors[row]
        vectors_layer.properties['color'] = colors
        vectors_layer.properties = dict(vectors_layer.properties)
    if row < len(vector_widths):
        del vector_widths[row]
    if row < len(vector_lengths):
        del vector_lengths[row]
    refresh_vector_table()

def save_vectors_to_file():
    data = []
    for i, vec in enumerate(vectors_layer.data):
        start, direction = vec
        color = vectors_layer.properties['color'][i] if 'color' in vectors_layer.properties else 'red'
        width = vector_widths[i] if i < len(vector_widths) else 3
        length = vector_lengths[i] if i < len(vector_lengths) else 1.0
        data.append({
            'start': start.tolist(),
            'direction': direction.tolist(),
            'edge_color': color,
            'edge_width': width,
            'length': length
        })
    with open(path_input.text(), 'w') as f:
        json.dump(data, f, indent=2)

def load_vectors_from_file():
    global vector_widths, vector_lengths
    with open(path_input.text(), 'r') as f:
        data = json.load(f)
    vectors = []
    colors = []
    vector_widths = []
    vector_lengths = []
    for item in data:
        vectors.append([np.array(item['start']), np.array(item['direction'])])
        colors.append(item['edge_color'])
        vector_widths.append(item.get('edge_width', 3))
        vector_lengths.append(item.get('length', 1.0))
    vectors_layer.data = np.array(vectors)
    vectors_layer.properties = {'color': colors}
    vectors_layer.edge_color = 'color'
    vectors_layer.edge_color_mode = 'cycle'
    refresh_vector_table()

def clear_vectors():
    vectors_layer.data = np.empty((0, 2, 3))
    vectors_layer.properties = {'color': []}
    vector_widths.clear()
    vector_lengths.clear()
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

def draw_vector(point, direction, length=25, color='red'):
    unit = direction / np.linalg.norm(direction)
    start = point - unit * length
    vector = np.array([[start, unit * length]])
    vectors_layer.data = np.concatenate([vectors_layer.data, vector], axis=0)
    if 'color' not in vectors_layer.properties:
        vectors_layer.properties = {'color': [color]}
    else:
        colors = list(vectors_layer.properties['color'])
        colors.append(color)
        vectors_layer.properties['color'] = colors
        vectors_layer.properties = dict(vectors_layer.properties)
    vector_widths.append(3)
    vector_lengths.append(1.0)
    vectors_layer.edge_color = 'color'
    vectors_layer.edge_color_mode = 'cycle'
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
            draw_vector(mid[[2,1,0]], np.array([0,1,1]), length=25, color='red')
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
