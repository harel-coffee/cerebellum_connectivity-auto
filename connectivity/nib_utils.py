# import packages
import os
from pathlib import Path
import nibabel as nib
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib as mpl
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
import SUITPy.flatmap as flatmap
from nilearn.plotting import view_surf, plot_surf_roi
from nilearn.surface import load_surf_data

import connectivity.constants as const
from connectivity import data as cdata

def make_label_gifti_cortex(data, anatomical_struct='CortexLeft', label_names=None, column_names=None, label_RGBA=None):
    """
    Generates a label GiftiImage from a numpy array
       @author joern.diedrichsen@googlemail.com, Feb 2019 (Python conversion: switt)

    INPUTS:
        data (np.array):
             numVert x numCol data
        anatomical_struct (string):
            Anatomical Structure for the Meta-data default= 'CortexLeft'
        label_names (list): 
            List of strings for label names
        column_names (list):
            List of strings for names for columns
        label_RGBA (list):
            List of rgba vectors
    OUTPUTS:
        gifti (label GiftiImage)

    """
    try:
        num_verts, num_cols = data.shape
    except: 
        data = np.reshape(data, (len(data),1))
        num_verts, num_cols  = data.shape

    num_labels = len(np.unique(data))

    # Create naming and coloring if not specified in varargin
    # Make columnNames if empty
    if column_names is None:
        column_names = []
        for i in range(num_labels):
            column_names.append("col_{:02d}".format(i+1))

    # Determine color scale if empty
    if label_RGBA is None:
        hsv = plt.cm.get_cmap('hsv',num_labels)
        color = hsv(np.linspace(0,1,num_labels))
        # Shuffle the order so that colors are more visible
        color = color[np.random.permutation(num_labels)]
        label_RGBA = np.zeros([num_labels,4])
        for i in range(num_labels):
            label_RGBA[i] = color[i]

    # Create label names
    if label_names is None:
        label_names = []
        for i in range(num_labels):
            label_names.append("label-{:02d}".format(i))

    # Create label.gii structure
    C = nib.gifti.GiftiMetaData.from_dict({
        'AnatomicalStructurePrimary': anatomical_struct,
        'encoding': 'XML_BASE64_GZIP'})


    num_labels = np.arange(num_labels)
    E_all = []
    for (label,rgba,name) in zip(num_labels,label_RGBA,label_names):
        E = nib.gifti.gifti.GiftiLabel()
        E.key = label 
        E.label= name
        E.red = rgba[0]
        E.green = rgba[1]
        E.blue = rgba[2]
        E.alpha = rgba[3]
        E.rgba = rgba[:]
        E_all.append(E)

    D = list()
    for i in range(num_cols):
        d = nib.gifti.GiftiDataArray(
            data=np.float32(data[:, i]),
            intent='NIFTI_INTENT_LABEL', 
            datatype='NIFTI_TYPE_INT32', # was NIFTI_TYPE_INT32
            meta=nib.gifti.GiftiMetaData.from_dict({'Name': column_names[i]})
        )
        D.append(d)

    # Make and return the gifti file
    gifti = nib.gifti.GiftiImage(meta=C, darrays=D)
    gifti.labeltable.labels.extend(E_all)
    return gifti

def make_func_gifti_cortex(data, anatomical_struct='CortexLeft', column_names=None):
    """
    Generates a function GiftiImage from a numpy array
       @author joern.diedrichsen@googlemail.com, Feb 2019 (Python conversion: switt)

    Args:
        data (np array): shape (vertices x columns) 
        anatomical_struct (str): Anatomical Structure for the Meta-data default='CortexLeft'
        column_names (list or None): List of strings for column names, default is None
    Returns:
        gifti (functional GiftiImage)
    """
    try:
        num_verts, num_cols = data.shape
    except: 
        data = np.reshape(data, (len(data),1))
        num_verts, num_cols  = data.shape
  
    # Make columnNames if empty
    if column_names is None:
        column_names = []
        for i in range(num_cols):
            column_names.append("col_{:02d}".format(i+1))

    C = nib.gifti.GiftiMetaData.from_dict({
    'AnatomicalStructurePrimary': anatomical_struct,
    'encoding': 'XML_BASE64_GZIP'})

    E = nib.gifti.gifti.GiftiLabel()
    E.key = 0
    E.label= '???'
    E.red = 1.0
    E.green = 1.0
    E.blue = 1.0
    E.alpha = 0.0

    D = list()
    for i in range(num_cols):
        d = nib.gifti.GiftiDataArray(
            data=np.float32(data[:, i]),
            intent='NIFTI_INTENT_NONE',
            datatype='NIFTI_TYPE_FLOAT32',
            meta=nib.gifti.GiftiMetaData.from_dict({'Name': column_names[i]})
        )
        D.append(d)

    gifti = nib.gifti.GiftiImage(meta=C, darrays=D)
    gifti.labeltable.labels.append(E)

    return gifti

def get_label_colors(fpath):
    """get rgba for atlas (given by fpath)

    Args: 
        fpath (str): full path to atlas
    Returns: 
        rgba (np array): shape num_labels x num_rgba
    """
    dirs = const.Dirs()

    img = nib.load(fpath)
    labels = img.labeltable.labels

    rgba = np.zeros((len(labels),4))
    for i,label in enumerate(labels):
        rgba[i,] = labels[i].rgba

    cmap = LinearSegmentedColormap.from_list('mylist', rgba)
    cmap = LinearSegmentedColormap.from_list('mylist', rgba, N=len(rgba))
    mpl.cm.register_cmap("mycolormap", cmap)
    cpal = sns.color_palette("mycolormap", n_colors=len(rgba))

    return rgba, cpal

def binarize_vol(imgs, metric='max'):
    """Binarizes niftis for `imgs` based on `metric`
    Args: 
        imgs (list of nib obj or list of str): list of nib objects or fullpath to niftis
        metric (str): 'max' or 'min'
    Returns: 
        nib obj
    """
    data_all = []
    for img in imgs:
        data_masked = cdata.read_suit_nii(img)
        data_all.append(data_masked)

    data = np.vstack(data_all)

    # binarize `data` based on max or min values
    if metric=='max':
        labels = np.argmax(data, axis=0)
    elif metric=='min':
        labels = np.argmin(data, axis=0)
    
    # compute 3D vol for `labels`
    nib_obj = cdata.convert_cerebellum_to_nifti(labels+1)

    return nib_obj[0]

def subtract_vol(imgs):
    """Binarizes niftis for `imgs` based on `metric`
    Args: 
        imgs (list of nib obj or list of str): list of nib objects or fullpath to niftis
    Returns: 
        nib obj
    """

    if len(imgs)>2:
        print(Exception('there should be no more than two nib objs in `imgs`'))

    data_all = []
    for img in imgs:
        data_masked = cdata.read_suit_nii(img)
        data_all.append(data_masked)

    data = np.vstack(data_all)

    data_diff = data[0] - data[1]
    
    # compute 3D vol for `labels`
    nib_obj = cdata.convert_cerebellum_to_nifti(data_diff)

    return nib_obj[0]

def get_cortical_atlases():
    """returns: fpaths (list of str): list to all cortical atlases (*.label.gii) 
    """
    dirs = const.Dirs()

    fpaths = []
    fpath = os.path.join(dirs.reg_dir, 'data', 'group')
    for path in list(Path(fpath).rglob('*.label.gii')):
        # if any(atlas_key in str(path) for atlas_key in atlas_keys):
        fpaths.append(str(path))

    return fpaths

def get_cerebellar_atlases():
    """returns: fpaths (list of str): list of full paths to cerebellar atlases
    """
    dirs = const.Dirs()

    fpaths = []
    # get atlases in cerebellar atlases
    fpath = os.path.join(dirs.base_dir, 'cerebellar_atlases')
    for path in list(Path(fpath).rglob('*.label.gii')):
        fpaths.append(str(path))
    
    return fpaths

def view_cerebellum(gifti, cscale=None, colorbar=True, title=True):
    """Visualize data on suit flatmap, plots either *.func.gii or *.label.gii data

    Args: 
        gifti (str): full path to gifti image
        cscale (list or None): default is None
        colorbar (bool): default is False.
    """

    # full path to surface
    surf_mesh = os.path.join(flatmap._surf_dir,'FLAT.surf.gii')

    # determine overlay
    if '.func.' in gifti:
        overlay_type = 'func'
    elif '.label.' in gifti:
        overlay_type = 'label'

    view = flatmap.plot(gifti, surf=surf_mesh, overlay_type=overlay_type, cscale=cscale, colorbar=True, new_figure=True) # implement colorbar

    if title:
        fname = Path(gifti).name
        view.set_title(fname.split('.')[0])

    return view

def view_cortex(gifti, hemisphere='R', cmap=None, cscale=None, atlas_type='inflated', symmetric_cmap=False, orientation='medial'):
    """Visualize data on inflated cortex, plots either *.func.gii or *.label.gii data

    Args: 
        gifti (str): fullpath to file: *.func.gii or *.label.gii
        bg_map (str or np array or None): 
        map_type (str): 'func' or 'label'
        hemisphere (str): 'R' or 'L'
        atlas_type (str): 'inflated', 'very_inflated' (see fs_LR dir)
    """
    # initialise directories
    dirs = const.Dirs()

    # get surface mesh
    surf_mesh = os.path.join(dirs.reg_dir, 'data', 'group', f'fs_LR.32k.{hemisphere}.{atlas_type}.surf.gii')

    # load surf data from file
    fname = Path(gifti).name
    title = fname.split('.')[0]
        
    # Determine scale
    func_data = load_surf_data(gifti)
    if ('.func.' in gifti and cscale is None):
        cscale = [np.nanmin(func_data), np.nanmax(func_data)]

    if '.func.' in gifti:
        view = view_surf(surf_mesh=surf_mesh, 
                        surf_map=func_data,
                        vmin=cscale[0], 
                        vmax=cscale[1],
                        cmap='CMRmap',
                        symmetric_cmap=symmetric_cmap,
                        # title=title
                        ) 
    elif '.label.' in gifti:   
        if hemisphere=='L':
            orientation = 'lateral'
        if cmap is None:
            _, cmap = get_label_colors(fpath=gifti)
        view = plot_surf_roi(surf_mesh, gifti, cmap=cmap, view=orientation)    
    
    return view
    
