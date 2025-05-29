import napari
import tifffile
import numpy as np
from qtpy.QtWidgets import QPushButton, QMenu
import pandas as pd
# from vispy.util.quaternion import Quaternion
# from vispy.visuals.transforms import ChainTransform

volume = tifffile.imread('recon_ss_single_0007.tiff')  # (z,x,y) i.e. (z,h,w)
print("Img size: ", volume.shape, "Img type: ", volume.dtype)

viewer = napari.Viewer(ndisplay=3)

layer = viewer.add_image(volume,
                         colormap='green',
                         scale=(5, 0.91, 0.91),
                         rendering='mip')

# Declare a 3D point layer explicitly
points_layer = viewer.add_points(np.empty((0, 3)),
                                 name="Triangulated Point",
                                 size=10,
                                 symbol='tailed_arrow',
                                 face_color='red')

ray_info = {'first': None, 'second': None}
measured_points = []  # 全局列表记录所有三角测量点

def get_camera_ray(event):
    # Get transformer: scene → canvas (vispy)
    view = viewer.window.qt_viewer.view
    canvas_transform = view.scene.transform

    # Get the canvas' coordination [pixel]
    pos_canvas = np.array(event.pos)
    print('canvas pos:', pos_canvas)

    # Construct near/far points (z=0 and z=1 represent depth normalized clipping planes)
    p_near = np.array([*pos_canvas, 0, 1])  # Homogeneous coordinates (x, y, z=0, 1)
    p_far = np.array([*pos_canvas, 1, 1])   # Homogeneous coordinates (x, y, z=1, 1)

    # Inverse map: screen → world
    world_near_h = canvas_transform.imap(p_near)
    world_far_h = canvas_transform.imap(p_far)

    # Homogeneous coordinates->Cartesian coordinates
    world_near = world_near_h[:3] / world_near_h[3]
    world_far = world_far_h[:3] / world_far_h[3]

    # print('world_near:', world_near)
    # print('world_far:', world_far)

    # Calculate the direction of the ray
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


def handle_right_click(layer, event):
    if event.button != 2:  # Right double click
        return
    pos, direction = get_camera_ray(event)

    # pop up the menu
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

        mid2 = mid[[2, 1, 0]]
        if mid2 is not None:
            print(f"Calculated 3D point coordination：{mid2}")
            points_layer.add([mid2])
            measured_points.append(mid2.tolist()) # 存储为 [z, y, x] 格式
        else:
            print("Failed to measure because rays are parallel.")
        ray_info['first'] = None
        ray_info['second'] = None


measured_points = []

def save_points_to_csv():
    if not measured_points:
        print("No triangulated points to save.")
        return
    df = pd.DataFrame(measured_points, columns=['Z', 'Y', 'X'])
    df.to_csv('triangulated_points.csv', index=False)
    print("Saved to 'triangulated_points.csv'.")

btn = QPushButton("Save Points")
btn.clicked.connect(save_points_to_csv)
viewer.window.add_dock_widget(btn, area='right')

layer.mouse_double_click_callbacks.append(handle_right_click)

napari.run()
