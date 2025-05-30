import napari
import tifffile
import numpy as np
import json, os, glob
from qtpy.QtWidgets import (
    QPushButton, QLineEdit, QVBoxLayout, QWidget,
    QTableWidget, QComboBox, QMenu, QDoubleSpinBox, QHBoxLayout, QSizePolicy, QFileDialog
)
from napari.utils.notifications import show_info


# === Predefined parameters ===
default_path = '.'
default_json_path = os.path.join(default_path, 'saved_vectors.json')
available_colors = [
    'red', 'green', 'blue', 'yellow', 'cyan', 'magenta',
    'orange', 'purple', 'lime', 'pink', 'brown', 'gray', 'black',
    'navy', 'teal', 'gold', 'salmon', 'indigo', 'olive', 'maroon'
]
image_pixel_size = (5, 0.91, 0.91)  # [z, y, x]
colormap = 'green'
default_arrow_length = 25
default_arrow_color = 'red'
default_arrow_width = 3
default_arrow_opacity = 1.0

snapshot_dir = os.path.join(default_path, 'snapshots')
os.makedirs(snapshot_dir, exist_ok=True)

tif_files = sorted(glob.glob(os.path.join(default_path, '*.tif')) + glob.glob(os.path.join(default_path, '*.tiff')))
tif_index = 0

viewer = napari.Viewer(ndisplay=3)
image_layer = None

def load_tif(index):
    """
    Load Tiff stack to canvas and load corresponding vector arrows according to json
    :param index: the sequence number of the current tiff in the folder
    """
    global image_layer
    if not tif_files:
        raise FileNotFoundError(f"No .tif or .tiff files found in directory: {default_path}")
    # display the tiff stack
    volume = tifffile.imread(tif_files[index])
    if 'TiffStack' in viewer.layers:
        viewer.layers.remove(image_layer)
    image_layer = viewer.add_image(volume, name='TiffStack', colormap=colormap, scale=image_pixel_size, rendering='mip')

    # Set the json file path and load corresponding vector arrows
    current_json = os.path.splitext(tif_files[index])[0] + '.json'
    save_path_input.setText(current_json)
    load_vectors_from_file(current_json)


def save_and_advance(index_delta):
    save_vectors_to_file()
    clear_vectors()
    global tif_index
    tif_index = (tif_index + index_delta + len(tif_files)) % len(tif_files)
    load_tif(tif_index)

# # Initialize GUI components
table = QTableWidget()
table.setColumnCount(11)
table.setHorizontalHeaderLabels([
    'End Z', 'End Y', 'End X',
    'Dir Z', 'Dir Y', 'Dir X',
    'Color', 'Length', 'Width', 'Opacity', 'Delete'
])
# Adjust column width of the table
for i in range(6):
    table.setColumnWidth(i, 60)
table.setColumnWidth(6, 70)
table.setColumnWidth(7, 50)
table.setColumnWidth(8, 50)
table.setColumnWidth(9, 55)
table.setColumnWidth(10, 65)

save_path_input = QLineEdit()
save_path_input.setText(default_json_path)

load_path_input= QLineEdit()
load_path_input.setText(default_json_path)

view_path_input = QLineEdit()
view_path_input.setPlaceholderText("Enter the view [.npz] file path")
view_path_input.setText(os.path.join(snapshot_dir, 'example_view.npz'))

# Define buttons
save_btn = QPushButton("Save Vectors")
load_btn = QPushButton("Load Vectors")
clear_btn = QPushButton("Clear Vectors")
prev_btn = QPushButton("Prev TIFF")
next_btn = QPushButton("Next TIFF")
sync_view_btn = QPushButton("Synchronous view")
change_path_btn = QPushButton("Select Folder")
snap_btn = QPushButton("Snapshot")


# === Global State ===
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
        print(f"Update opacity failed: {e}")

def update_width_from_table(row):
    try:
        new_width = table.cellWidget(row, 8).value()
        vector_layers[row].edge_width = new_width
    except Exception as e:
        print(f"Update width failed：{e}")

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
        print(f"Update length failed：{e}")


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


def change_default_path():
    """
    Triggered after the change_path_btn button clicked.
    Change the entire workdir where all tiff stacks are located.
    """
    global default_path, default_json_path, snapshot_dir, tif_files, tif_index

    new_path = QFileDialog.getExistingDirectory(None, "Select the new tiff stack folder", default_path)
    if not new_path:
        return

    default_path = new_path
    default_json_path = os.path.join(default_path, 'saved_vectors.json')
    snapshot_dir = os.path.join(default_path, 'snapshots')
    os.makedirs(snapshot_dir, exist_ok=True)

    tif_files = sorted(glob.glob(os.path.join(default_path, '*.tif')) + glob.glob(os.path.join(default_path, '*.tiff')))
    tif_index = 0

    if not tif_files:
        show_info("TIFF file not found in new path")
        return

    save_path_input.setText(os.path.splitext(tif_files[0])[0] + '.json')
    load_path_input.setText(os.path.splitext(tif_files[0])[0] + '.json')
    load_tif(tif_index)
    show_info(f"The path has been updated to: {default_path}")


def delete_vector(row):
    """
    Triggered after the clear button clicked.
    Delete the vector record in table and the corresponding vector layer.
    """
    vec_layer = vector_layers.pop(row)
    viewer.layers.remove(vec_layer)
    if row < len(color_values):
        color_values.pop(row)
    refresh_vector_table()


def save_vectors_to_file():
    """
    Triggered after the save button clicked.
    Convert the information in table to json formate and save to the specified path (save_path_input).
    """
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
    json_path = save_path_input.text()
    if not data and os.path.exists(json_path):
        print("No vector arrows added. Skipping saving to avoid overwriting existing JSON.")
        return
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

def load_vectors_from_file(json_path=None):
    """
    Not a slot function of any button.
    Only called when switching stacks.
    """
    clear_vectors()
    if json_path is None:
        json_path = save_path_input.text()  # 从文本框读取

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
        print(f"[WARN] JSON file dose not exist：{json_path}")

def load_vectors_from_other_file():
    """
    Triggered after the load button clicked.
    Load the json information of specified path (load_path_input) into table
    and generate corresponding vector layers.
    """
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
        print(f"[WARN] JSON file does not exist: {json_path}")


def clear_vectors():
    """
    Triggered after the clear button clicked.
    Clear all vector arrows' information and corresponding vector layers.
    """
    for vec_layer in vector_layers:
        viewer.layers.remove(vec_layer)
    vector_layers.clear()
    color_values.clear()
    refresh_vector_table()


def get_camera_ray(event):
    """
    Get the function of a space line: p0 + t * dir t \in (-\infty, +\infty)
    based on the location where the mouse is clicked
    :return near: the coordinate of p0 (x,y,z)
    :return dir / np.linalg.norm(dir): the normalized direction of the line (x,y,z)
    """
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
    """
    Get the coordinates of the closest point between two non-coplanar lines
    """
    w0 = p1 - p2
    a, b, c = np.dot(d1, d1), np.dot(d1, d2), np.dot(d2, d2)
    d, e = np.dot(d1, w0), np.dot(d2, w0)
    denom = a * c - b * b
    if np.isclose(denom, 0): return None
    t, s = (b * e - c * d) / denom, (a * e - b * d) / denom
    return (p1 + t * d1 + p2 + s * d2) / 2


# default_arrow_length = 25
# default_arrow_color = 'red'
# default_arrow_width = 3
# default_arrow_opacity = 1.0
def draw_vector(point, direction,
                length=default_arrow_length,
                color=default_arrow_color,
                width=default_arrow_width,
                refresh=True,
                opacity=default_arrow_opacity):
    """
    Add vector layer containing an arrow difined by the return result
    of function triangulate_rays and the predefined direction.
    """
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


def next_tif():
    """
    Triggered after the next button clicked.
    """
    save_and_advance(1)

def prev_tif():
    """
    Triggered after the prev button clicked.
    """
    save_and_advance(-1)

def save_snapshot_and_view():
    """
    Triggered after the snap button clicked.
    """
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
        show_info(f"Saved images and perspectives: {snapshot_path}")
    except Exception as e:
        show_info(f"Fail to save: {e}")


def restore_view_from_textbox():
    """
    Triggered after the sync view button clicked.
    """
    path = view_path_input.text()
    if not os.path.exists(path):
        show_info(f"The view file does not exist：{path}")
        return
    try:
        params = np.load(path)
        dims_point = params['dims_point']
        for i, val in enumerate(dims_point):
            viewer.dims.set_point(i, val)
        viewer.camera.center = params['cam_center']
        viewer.camera.angles = params['cam_angles']
        viewer.camera.zoom = params['cam_zoom']
        show_info(f"View restored：{path}")
    except Exception as e:
        show_info(f"View restoration failed: {e}")



save_btn.clicked.connect(save_vectors_to_file)
snap_btn.clicked.connect(save_snapshot_and_view)
clear_btn.clicked.connect(clear_vectors)
prev_btn.clicked.connect(prev_tif)
next_btn.clicked.connect(next_tif)
sync_view_btn.clicked.connect(restore_view_from_textbox)
change_path_btn.clicked.connect(change_default_path)
load_btn.clicked.connect(load_vectors_from_other_file)

# save_btn = QPushButton("Save Vectors", clicked=save_vectors_to_file)
# snap_btn = QPushButton("Snapshot", clicked=save_snapshot_and_view)
# load_btn = QPushButton("Load Vectors", clicked=load_vectors_from_other_file)
# clear_btn = QPushButton("Clear Vectors", clicked=clear_vectors)
# prev_btn = QPushButton("Prev TIFF", clicked=prev_tif)
# next_btn = QPushButton("Next TIFF", clicked=next_tif)
# sync_view_btn = QPushButton("Synchronous view", clicked=restore_view_from_textbox)
# change_path_btn = QPushButton("Select Folder", clicked=change_default_path)

# === UI layout ===
controls = QWidget()
layout = QVBoxLayout()

layout.addWidget(change_path_btn)
# Save JSON Path + Save Vectors
hlayout1 = QHBoxLayout()
hlayout1.addWidget(save_path_input)
hlayout1.addWidget(save_btn)
layout.addLayout(hlayout1)

# Load JSON Path + Load Vectors Btn
hlayout2 = QHBoxLayout()
hlayout2.addWidget(load_path_input)
hlayout2.addWidget(load_btn)
layout.addLayout(hlayout2)

# View Path Box + Sync View Button
hlayout3 = QHBoxLayout()
hlayout3.addWidget(view_path_input)
hlayout3.addWidget(sync_view_btn)
layout.addLayout(hlayout3)

layout.addWidget(clear_btn)

# Prev and Next side by side
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
