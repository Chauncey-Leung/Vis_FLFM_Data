"""添加矢量箭头的版本 这样箭头的姿态就可以调整了"""

import napari
import tifffile
import numpy as np
import pandas as pd
from qtpy.QtWidgets import QPushButton, QMenu, QVBoxLayout, QWidget, QLineEdit
import os
import json

volume = tifffile.imread('recon_ss_single_0007.tiff')  # (z,x,y) i.e. (z,h,w)
print(volume.shape, volume.dtype)

viewer = napari.Viewer(ndisplay=3)

layer = viewer.add_image(volume,
                         colormap='green',
                         scale=(5, 0.91, 0.91),
                         rendering='mip')

# Triangulated point layer (Z, Y, X)
# 单纯用来验证矢量添加得是否正确
# points_layer = viewer.add_points(np.empty((0, 3)),
#                                  name="Triangulated Point",
#                                  size=5,
#                                  symbol='ring',
#                                  face_color='red')

# Vectors layer for ray directions
vectors_layer = viewer.add_vectors(np.empty((0, 2, 3)),
                                   edge_color='red',
                                   vector_style='arrow',
                                   name="Arrow_vector",
                                   edge_width=3,
                                   length=1,
                                   opacity=1.0
                                   )

# Store triangulated points for export
measured_points = []
# Temporary storage for ray info
ray_info = {'first': None, 'second': None}


def get_camera_ray(event):
    view = viewer.window.qt_viewer.view
    canvas_transform = view.scene.transform

    pos_canvas = np.array(event.pos)
    print('canvas pos:', pos_canvas)

    p_near = np.array([*pos_canvas, 0, 1])
    p_far = np.array([*pos_canvas, 1, 1])

    world_near_h = canvas_transform.imap(p_near)
    world_far_h = canvas_transform.imap(p_far)

    world_near = world_near_h[:3] / world_near_h[3]
    world_far = world_far_h[:3] / world_far_h[3]

    direction = world_far - world_near
    direction /= np.linalg.norm(direction)
    print('direction:', direction)

    return world_near.copy(), direction.copy()


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

    point1 = p1 + t * d1
    point2 = p2 + s * d2
    return (point1 + point2) / 2


def draw_vector(target_point, direction, length_scale=25):
    """添加一个矢量箭头到 Vectors 图层"""
    unit_direction = direction / np.linalg.norm(direction)
    start_point = target_point - unit_direction * length_scale

    vector = np.array([[start_point, target_point-start_point]])
    if len(vectors_layer.data) == 0:
        vectors_layer.data = vector
    else:
        vectors_layer.data = np.concatenate([vectors_layer.data, vector], axis=0)
    # if len(vectors_layer.data) == 1 and np.allclose(vectors_layer.data[0], [[[0, 0, 0], [0, 0, 1]]]):
    #     vectors_layer.data = np.array([vector])  # 清除默认再加你自己的
    # elif len(vectors_layer.data) == 0:
    #     vectors_layer.data = vector
    # else:
    #     vectors_layer.data = np.concatenate([vectors_layer.data, vector], axis=0)


def handle_right_click(layer, event):
    if event.button != 2:
        return

    pos, direction = get_camera_ray(event)

    menu = QMenu()
    act1 = menu.addAction("First Click")
    act2 = menu.addAction("Second Click")
    action = menu.exec_(event.native.globalPos())

    if action == act1:
        ray_info['first'] = (pos.copy(), direction.copy())
        print("First click recorded")
    elif action == act2:
        ray_info['second'] = (pos.copy(), direction.copy())
        print("Second click recorded")

    if ray_info['first'] and ray_info['second']:
        p1, d1 = ray_info['first']
        p2, d2 = ray_info['second']
        mid = triangulate_rays(p1, d1, p2, d2)

        if mid is not None:
            mid2 = mid[[2, 1, 0]]  # convert to ZYX
            print(f"Triangulated point: {mid2}")
            # points_layer.add([mid2])
            draw_vector(mid2, np.array([0, 1, 1]))  # 添加矢量箭头
            measured_points.append(mid2.tolist())
        else:
            print("Rays are parallel, triangulation failed.")

        ray_info['first'] = None
        ray_info['second'] = None


def save_vectors_to_file():
    if len(vectors_layer.data) == 0:
        print("No vectors to save.")
        return

    # 每条矢量：起点和方向（napari 是 (N, 2, 3)）
    vector_data = []
    for vec in vectors_layer.data:
        start = vec[0]
        direction = vec[1]
        end = start + direction

        vector_data.append({
            'start': start.tolist(),
            'end': end.tolist(),
            'direction': direction.tolist(),
            'edge_color': vectors_layer.edge_color.name if hasattr(vectors_layer.edge_color, 'name') else str(vectors_layer.edge_color),
            'edge_width': vectors_layer.edge_width,
            'length': vectors_layer.length,
            'vector_style': vectors_layer.vector_style,
        })

    with open('saved_vectors.json', 'w') as f:
        json.dump(vector_data, f, indent=2)

    print(f"Saved {len(vector_data)} vectors to 'saved_vectors.json'")

# ---- 清空矢量箭头 ----
def clear_vectors():
    vectors_layer.data = np.empty((0, 2, 3))
    print("Vectors cleared.")


# ---- 从 JSON 恢复矢量箭头 ----
def load_vectors_from_file():
    load_path = path_input.text().strip() or os.path.join(default_path, 'saved_vectors.json')

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
    vectors_layer.edge_color = vec.get('edge_color', 'red')
    vectors_layer.edge_width = vec.get('edge_width', 2)
    vectors_layer.length = vec.get('length', 1)
    vectors_layer.vector_style = vec.get('vector_style', 'arrow')

    print(f"Loaded {len(vectors)} vectors from '{load_path}'")


# 添加按钮用于保存点
save_vectors_button  = QPushButton("Save Vectors")
save_vectors_button.clicked.connect(save_vectors_to_file)


default_path = os.path.dirname(os.path.abspath('recon_ss_single_0007.tiff'))
# ---- 文本框输入：JSON 文件路径 ----
path_input = QLineEdit()
path_input.setPlaceholderText("保存/加载路径（默认：tif同目录）")
path_input.setText(os.path.join(default_path, 'saved_vectors.json'))


clear_vectors_button = QPushButton("Clear Vectors")
clear_vectors_button.clicked.connect(clear_vectors)

load_vectors_button = QPushButton("Load Vectors")
load_vectors_button.clicked.connect(load_vectors_from_file)

# ---- 添加控件到 Napari dock ----
controls_widget = QWidget()
layout = QVBoxLayout()
layout.addWidget(path_input)
layout.addWidget(save_vectors_button)
layout.addWidget(load_vectors_button)
layout.addWidget(clear_vectors_button)
controls_widget.setLayout(layout)

viewer.window.add_dock_widget(controls_widget, area='right')

# 绑定右键双击事件
layer.mouse_double_click_callbacks.append(handle_right_click)

napari.run()
