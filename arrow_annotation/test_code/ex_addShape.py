import napari
import tifffile
import numpy as np
import pandas as pd
from qtpy.QtWidgets import QPushButton, QMenu

# 读取三维图像数据
volume = tifffile.imread('recon_ss_single_0007.tiff')  # (z,x,y)
print(volume.shape, volume.dtype)

viewer = napari.Viewer(ndisplay=3)
layer = viewer.add_image(volume, colormap='green', scale=(5, 0.91, 0.91), rendering='mip')

# Declare a 3D point layer explicitly
points_layer = viewer.add_points(np.empty((0, 3)),
                                 name="Triangulated Point",
                                 size=10,
                                 symbol='tailed_arrow',
                                 face_color='red')

# 用于显示交互式箭头的可编辑线段图层
arrows_layer = viewer.add_shapes(
    np.empty((0, 2, 3)),
    shape_type='line',
    edge_color='magenta',
    edge_width=2,
    name='Editable Arrows'
)

# 存储三角测量点
measured_points = []
ray_info = {'first': None, 'second': None}


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
    """两条射线的最短距离中点作为估算点"""
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


def draw_editable_arrow(p1, direction, length=20):
    """添加一个可以拖动姿态的箭头（线段）"""
    p2 = p1 + direction * length
    p1_zyx = p1[[2, 1, 0]]
    p2_zyx = p2[[2, 1, 0]]
    arrow = np.array([p1_zyx, p2_zyx])
    # arrow = [p1[[2, 1, 0]], p2[[2, 1, 0]]]  # napari 坐标为 Z,Y,X
    if len(arrows_layer.data) == 0:
        arrows_layer.data = np.array([arrow])
    else:
        arrows_layer.data = np.concatenate([arrows_layer.data, [arrow]], axis=0)


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
        print("✔ First click recorded")
    elif action == act2:
        ray_info['second'] = (pos.copy(), direction.copy())
        print("✔ Second click recorded")

    if ray_info['first'] and ray_info['second']:
        p1, d1 = ray_info['first']
        p2, d2 = ray_info['second']
        mid = triangulate_rays(p1, d1, p2, d2)
        if mid is not None:
            mid2 = mid[[2, 1, 0]]  # ZYX顺序
            points_layer.add([mid2])
            measured_points.append(mid2.tolist())
            draw_editable_arrow(mid, np.array([0,10,0]))
            print(f"Triangulated point: {mid2}")
        else:
            print("Rays are parallel. Cannot triangulate.")
        ray_info['first'] = None
        ray_info['second'] = None


def save_points_to_csv():
    if not measured_points:
        print("⚠ No triangulated points to save.")
        return
    df = pd.DataFrame(measured_points, columns=['Z', 'Y', 'X'])
    df.to_csv('triangulated_points.csv', index=False)
    print("✅ Saved to 'triangulated_points.csv'")


def clear_arrows():
    arrows_layer.data = np.empty((0, 2, 3))
    print("🧹 Arrows cleared.")


# 添加功能按钮
btn_save = QPushButton("💾 Save Points")
btn_save.clicked.connect(save_points_to_csv)
viewer.window.add_dock_widget(btn_save, area='right')

btn_clear = QPushButton("🧹 Clear Arrows")
btn_clear.clicked.connect(clear_arrows)
viewer.window.add_dock_widget(btn_clear, area='right')

# 注册右键点击回调
layer.mouse_double_click_callbacks.append(handle_right_click)

napari.run()
