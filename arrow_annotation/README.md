# Napari-arrow-annotation-app

An interactive 3D image and vector arrow visualization tool built on [Napari](https://napari.org/).

## Features

- Load and browse multi-frame 3D TIFF stacks
- Visualize editable vector arrows (direction, length, color, width, opacity)
- Edit vectors in a GUI table with live updates
- Save/load vector annotations in JSON format
- Snapshot current view and camera settings (npz)
- Fully object-oriented, modular, and extensible design

---

## Project Structure

```
arrow_annotation/
├── main_app.py          # Main application and UI layout
├── vector_arrow.py      # VectorArrow and ArrowManager classes
├── tiff_manager.py      # TIFF image loading and navigation
```

---

## Installation


```bash
conda create -n napari-vector python=3.9 -y
conda activate napari-vector
pip install -r requirements.txt
```
---

## Running the Application

```bash
python main_app.py
```
