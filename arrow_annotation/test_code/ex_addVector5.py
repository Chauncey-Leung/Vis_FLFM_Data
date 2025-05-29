import napari
import tifffile
import numpy as np
import json, os
from qtpy.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QTableWidget, QComboBox, QMenu, QDoubleSpinBox, QHBoxLayout, QSizePolicy
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
table.setColumnCount(11)
table.setHorizontalHeaderLabels([
    'End Z', 'End Y', 'End X',
    'Dir Z', 'Dir Y', 'Dir X',
    'Color', 'Length', 'Width', 'Opacity', 'Delete'
])
for i in range(6):
    table.setColumnWidth(i, 60)
table.setColumnWidth(6, 70)
table.setColumnWidth(7, 50)
table.setColumnWidth(8, 50)
table.setColumnWidth(9, 55)
table.setColumnWidth(10, 65)

path_input = QLineEdit()
path_input.setText(default_json_path)

# === 全局状态 ===
is_updating_table = False
ray_info = {'first': None, 'second': None}
vector_layers = []
color_boxes = []
color_values = []

# === 函数定义 ===
def update_opacity_from_table(row):
    try:
        new_opacity = table.cellWidget(row, 9).value()
        vector_layers[row].opacity = new_opacity
    except Exception as e:
        print(f"更新透明度失败：{e}")

def update_width_from_table(row):
    try:
        new_width = table.cellWidget(row, 8).value()
        vector_layers[row].edge_width = new_width
    except Exception as e:
        print(f"更新宽度失败：{e}")

def update_length_from_table(row):
    try:
        new_length = table.cellWidget(row, 7).value()
        vec_layer = vector_layers[row]
        vec = vec_layer.data[0]
        direction = vec[1] / np.linalg.norm(vec[1])
        end = vec[0] + vec[1]
        new_start = end - direction * new_length
        vec_layer.data = np.array([[new_start, direction * new_length]])
    except Exception as e:
        print(f"更新长度失败：{e}")

def refresh_vector_table():
    global is_updating_table, color_boxes
    is_updating_table = True
    color_boxes = []
    try:
        table.blockSignals(True)
        table.setRowCount(len(vector_layers))
        for i, vec_layer in enumerate(vector_layers):
            vec = vec_layer.data[0]
            start, delta = vec
            end = start + delta

            for j, val in enumerate(end):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(-9999, 9999)
                spin.setValue(val)
                spin.setFixedWidth(60)
                spin.valueChanged.connect(lambda _, row=i: update_vector_from_table(row))
                table.setCellWidget(i, j, spin)

            for j, val in enumerate(delta):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(-9999, 9999)
                spin.setValue(val)
                spin.setFixedWidth(60)
                spin.valueChanged.connect(lambda _, row=i: update_vector_from_table(row))
                table.setCellWidget(i, 3 + j, spin)

            color_box = QComboBox()
            color_box.addItems(available_colors)
            color = color_values[i] if i < len(color_values) else vec_layer.edge_color
            color_box.setCurrentText(color)
            color_box.currentTextChanged.connect(lambda _, row=i: update_color_from_table(row))
            table.setCellWidget(i, 6, color_box)
            color_boxes.append(color_box)

            length_spin = QDoubleSpinBox()
            length_spin.setDecimals(2)
            length_spin.setRange(0.1, 1000)
            length_spin.setValue(np.linalg.norm(vec[1]))
            length_spin.setFixedWidth(50)
            length_spin.valueChanged.connect(lambda _, row=i: update_length_from_table(row))
            table.setCellWidget(i, 7, length_spin)

            width_spin = QDoubleSpinBox()
            width_spin.setDecimals(2)
            width_spin.setRange(0.1, 50)
            width_spin.setValue(vec_layer.edge_width)
            width_spin.setFixedWidth(50)
            width_spin.valueChanged.connect(lambda _, row=i: update_width_from_table(row))
            table.setCellWidget(i, 8, width_spin)

            opacity_spin = QDoubleSpinBox()
            opacity_spin.setDecimals(2)
            opacity_spin.setRange(0.0, 1.0)
            opacity_spin.setSingleStep(0.05)
            opacity_spin.setValue(vec_layer.opacity)
            opacity_spin.setFixedWidth(55)
            opacity_spin.valueChanged.connect(lambda _, row=i: update_opacity_from_table(row))
            table.setCellWidget(i, 9, opacity_spin)

            del_btn = QPushButton("Delete")
            del_btn.setFixedWidth(60)
            del_btn.clicked.connect(lambda _, row=i: delete_vector(row))
            table.setCellWidget(i, 10, del_btn)
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
    end = np.array([table.cellWidget(row, j).value() for j in range(3)])
    direction = np.array([table.cellWidget(row, j).value() for j in range(3, 6)])
    start = end - direction
    vector_layers[row].data = np.array([[start, direction]])

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
        end = start + direction
        color = color_values[i] if i < len(color_values) else vec_layer.edge_color
        length = np.linalg.norm(direction)
        data.append({
            'end': end.tolist(),
            'direction': direction.tolist(),
            'edge_color': color,
            'edge_width': vec_layer.edge_width,
            'length': length,
            'opacity': vec_layer.opacity
        })
    with open(path_input.text(), 'w') as f:
        json.dump(data, f, indent=2)

def load_vectors_from_file():
    clear_vectors()
    with open(path_input.text(), 'r') as f:
        data = json.load(f)
    for item in data:
        end = np.array(item['end'])
        direction = np.array(item['direction'])
        start = end - direction
        draw_vector(
            point=end,
            direction=direction,
            length=item.get('length', np.linalg.norm(direction)),
            color=item.get('edge_color', 'red'),
            width=item.get('edge_width', 3),
            refresh=False,
            opacity=item.get('opacity', 1.0)
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

def draw_vector(point, direction, length=25, color='red', width=3, refresh=True, opacity=1.0):
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
    vec_layer.opacity = opacity
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
controls.setMinimumWidth(700)  # 设置右侧控件区宽度
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
