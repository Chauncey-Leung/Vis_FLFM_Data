# -*- coding: utf-8 -*-
"""
tiff_manager.py : Manage loading and switching between TIFF stacks for Napari

Copyright (c) 2025 Qianxi Liang (Peking University)

This software is licensed under the MIT License.
You may obtain a copy of the License at

    https://opensource.org/licenses/MIT

Author: Qianxi Liang
Affiliation: Peking University
Date: 2025-05-29
Description:
    This module defines a TIFFManager class that handles loading, navigation,
    and integration of multi-frame TIFF files with Napari image viewer.
"""

import os
import glob
import tifffile


class TIFFManager:
    def __init__(self, viewer, folder_path, json_path, load_callback):
        self.viewer = viewer
        self.folder_path = folder_path
        self.load_callback = load_callback
        self.files = []
        self.index = 0
        self.image_layer = None
        self.reload_file_list()
        self.json_path = json_path

    def reload_file_list(self):
        self.files = sorted(glob.glob(os.path.join(self.folder_path, '*.tif')) +
                            glob.glob(os.path.join(self.folder_path, '*.tiff')))
        self.index = 0

    def get_current_file_name(self):
        if not self.files:
            return ''
        return self.files[self.index]

    def load_current(self):
        if not self.files:
            return
        file = self.files[self.index]
        volume = tifffile.imread(file)
        if self.image_layer:
            self.viewer.layers.remove(self.image_layer)
        from main_app import image_pixel_size, default_colormap
        self.image_layer = self.viewer.add_image(
            volume, name='TiffStack',
            colormap=default_colormap,
            scale=image_pixel_size,
            rendering='mip')
        self.json_path = os.path.splitext(file)[0] + '.json'
        self.load_callback(self.json_path)

    def next(self):
        if not self.files:
            return
        self.index = (self.index + 1) % len(self.files)
        self.load_current()

    def prev(self):
        if not self.files:
            return
        self.index = (self.index - 1 + len(self.files)) % len(self.files)
        self.load_current()
