import napari
import tifffile
import numpy as np
import json, os, glob
from qtpy.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QTableWidget, QComboBox, QMenu, QDoubleSpinBox, QHBoxLayout, QSizePolicy, QFileDialog
)
from napari.utils.notifications import show_info


# === 初始化 ===
default_tiff = r'F:\可视化\2-dark-recon\recon_ss_single_0007.tiff'
default_path = os.path.dirname(os.path.abspath(default_tiff))
default_json_path = os.path.join(default_path, 'saved_vectors.json')
available_colors = [
    'red', 'green', 'blue', 'yellow', 'cyan', 'magenta',
    'orange', 'purple', 'lime', 'pink', 'brown', 'gray', 'black',
    'navy', 'teal', 'gold', 'salmon', 'indigo', 'olive', 'maroon'
]

# todo: 存在性检查
snapshot_dir = os.path.join(default_path, 'snapshots')
os.makedirs(snapshot_dir, exist_ok=True)

tif_files = sorted(glob.glob(os.path.join(default_path, '*.tif')) + glob.glob(os.path.join(default_path, '*.tiff')))
tif_index = 0

viewer = napari.Viewer(ndisplay=3)
image_layer = None

def load_tif(index):
    global image_layer
    if not tif_files:
        raise FileNotFoundError(f"No .tif or .tiff files found in directory: {default_path}")

    volume = tifffile.imread(tif_files[index])

    if 'Image' in viewer.layers:
        viewer.layers.remove(image_layer)

    image_layer = viewer.add_image(volume, name='Image', colormap='green', scale=(5, 0.91, 0.91), rendering='mip')

    # 设置 json 路径并加载对应矢量
    current_json = os.path.splitext(tif_files[index])[0] + '.json'
    path_input.setText(current_json)
    load_vectors_from_file(current_json)


def save_and_advance(index_delta):
    save_vectors_to_file()      # 保存当前箭头
    clear_vectors()             # 清除当前矢量
    global tif_index
    tif_index = (tif_index + index_delta + len(tif_files)) % len(tif_files)
    load_tif(tif_index)         # 加载图像 & 自动加载对应 json

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

load_path_input= QLineEdit()
load_path_input.setText(default_json_path)

# === 全局状态 ===
is_updating_table = False
ray_info = {'first': None, 'second': None}
vector_layers = []
color_boxes = []
color_values = []

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
    json_path = path_input.text()
    if not data and os.path.exists(json_path):
        print("当前无矢量数据，跳过保存，避免覆盖已有 JSON。")
        return
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

def load_vectors_from_file(json_path=None):
    clear_vectors()
    if json_path is None:
        json_path = path_input.text()  # 从文本框读取

    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        for item in data:
            end = np.array(item['end'])
            direction = np.array(item['direction'])
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
    else:
        print(f"[WARN] JSON 文件不存在：{json_path}")

def load_vectors_from_other_file():
    json_path = load_path_input.text()  # 从文本框读取
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            data = json.load(f)
        for item in data:
            end = np.array(item['end'])
            direction = np.array(item['direction'])
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
    else:
        print(f"[WARN] JSON 文件不存在：{json_path}")


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
            draw_vector(mid[[2, 1, 0]], np.array([0, 1, 1]), length=25, color='red', width=3)
        ray_info['first'] = ray_info['second'] = None




# === UI 布局 ===
def next_tif():
    save_and_advance(1)

def prev_tif():
    save_and_advance(-1)


def save_snapshot_and_view():
    # 文件名（仅 base name 部分）
    base_name = os.path.splitext(os.path.basename(tif_files[tif_index]))[0]
    snapshot_path = os.path.join(snapshot_dir, f'{base_name}_snapshot.png')
    view_path = os.path.join(snapshot_dir, f'{base_name}_view.npz')
    try:
        viewer.screenshot(snapshot_path, canvas_only=True, scale=4)
        np.savez(view_path,
                 dims_point=viewer.dims.point,
                 cam_center=viewer.camera.center,
                 cam_angles=viewer.camera.angles,
                 cam_zoom=viewer.camera.zoom)
        show_info(f"已保存图像和视角：{snapshot_path}")
    except Exception as e:
        show_info(f"保存失败: {e}")


def restore_view_from_textbox():
    path = view_path_input.text()
    if not os.path.exists(path):
        show_info(f"视角文件不存在：{path}")
        return
    try:
        params = np.load(path)
        dims_point = params['dims_point']
        for i, val in enumerate(dims_point):
            viewer.dims.set_point(i, val)
        viewer.camera.center = params['cam_center']
        viewer.camera.angles = params['cam_angles']
        viewer.camera.zoom = params['cam_zoom']
        show_info(f"已恢复视角：{path}")
    except Exception as e:
        show_info(f"视角恢复失败: {e}")

# 文本框用于输入视角文件路径
view_path_input = QLineEdit()
view_path_input.setPlaceholderText("Enter the view [.npz] file path")
view_path_input.setText(os.path.join(snapshot_dir, 'example_view.npz'))  # 可选预填路径

save_btn = QPushButton("Save Vectors", clicked=save_vectors_to_file)
snap_btn = QPushButton("Snapshot", clicked=save_snapshot_and_view)
load_btn = QPushButton("Load Vectors", clicked=load_vectors_from_other_file)
clear_btn = QPushButton("Clear Vectors", clicked=clear_vectors)
prev_btn = QPushButton("Prev TIFF", clicked=prev_tif)
next_btn = QPushButton("Next TIFF", clicked=next_tif)
sync_view_btn = QPushButton("Synchronous view", clicked=restore_view_from_textbox)


# 主控件布局
controls = QWidget()
layout = QVBoxLayout()

# Save JSON Path + Save Vectors
hlayout1 = QHBoxLayout()
hlayout1.addWidget(path_input)
hlayout1.addWidget(save_btn)
layout.addLayout(hlayout1)

# Load JSON Path + Load Vectors Btn
hlayout2 = QHBoxLayout()
hlayout2.addWidget(load_path_input)
hlayout2.addWidget(load_btn)
layout.addLayout(hlayout2)


# 视角路径框 + 同步按钮
hlayout3 = QHBoxLayout()
hlayout3.addWidget(view_path_input)
hlayout3.addWidget(sync_view_btn)
layout.addLayout(hlayout3)



layout.addWidget(clear_btn)

# Prev 和 Next 并排
hlayout4 = QHBoxLayout()
hlayout4.addWidget(prev_btn)
hlayout4.addWidget(next_btn)
layout.addLayout(hlayout4)

layout.addWidget(snap_btn)

layout.addWidget(table)

controls.setLayout(layout)
controls.setMinimumWidth(720)
viewer.window.add_dock_widget(controls, area='right')


load_tif(tif_index)
image_layer.mouse_double_click_callbacks.append(handle_right_click)
napari.run()
