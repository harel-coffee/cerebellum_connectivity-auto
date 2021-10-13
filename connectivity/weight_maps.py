# import libraries
import os
import numpy as np
import nibabel as nib
import pandas as pd
from nilearn.image import concat_imgs
import glob
from random import seed, sample
import deepdish as dd
from scipy.stats import mode
from SUITPy import flatmap, atlas

import connectivity.constants as const
import connectivity.io as cio
from connectivity import model
from connectivity import data as cdata
from connectivity import nib_utils as nio
from connectivity import sparsity as csparse
from connectivity.visualize import get_best_models

def split_subjects(
    subj_ids, 
    test_size=0.3
    ):
    """Randomly divide subject list into train and test subsets.

    Train subjects are used to train, validate, and test models(s).
    Test subjects are kept until the end of the project to evaluate
    the best (and final) model.

    Args:
        subj_ids (list): list of subject ids (e.g., ['s01', 's02'])
        test_size (int): size of test set
    Returns:
        train_subjs (list of subject ids), test_subjs (list of subject ids)
    """
    # set random seed
    seed(1)

    # get number of subjects in test (round down)
    num_in_test = int(np.floor(test_size * len(subj_ids)))

    # select test set
    test_subjs = list(sample(subj_ids, num_in_test))
    train_subjs = list([x for x in subj_ids if x not in test_subjs])

    return train_subjs, test_subjs

def save_maps_cerebellum(
    data, 
    fpath='/',
    group='nanmean', 
    gifti=True, 
    nifti=True, 
    column_names=[], 
    label_RGBA=[],
    label_names=[],
    ):
    """Takes data (np array), averages along first dimension
    saves nifti and gifti map to disk

    Args: 
        data (np array): np array of shape (N x 6937)
        fpath (str): save path for output file
        group (bool): default is 'nanmean' (for func data), other option is 'mode' (for label data) 
        gifti (bool): default is True, saves gifti to fpath
        nifti (bool): default is False, saves nifti to fpath
        column_names (list):
        label_RGBA (list):
        label_names (list):
    Returns: 
        saves nifti and/or gifti image to disk, returns gifti
    """
    num_cols, num_vox = data.shape

    # get mean or mode of data along first dim (first dim is usually subjects)
    if group=='nanmean':
        data = np.nanmean(data, axis=0)
    elif group=='mode':
        data = mode(data, axis=0)
        data = data.mode[0]
    else:
        print('need to group data by passing "nanmean" or "mode"')

    # convert averaged cerebellum data array to nifti
    nib_obj = cdata.convert_cerebellum_to_nifti(data=data)[0]
    
    # save nifti(s) to disk
    if nifti:
        nib.save(nib_obj, fpath + '.nii')

    # map volume to surface
    surf_data = flatmap.vol_to_surf([nib_obj], space="SUIT", stats=group)

    # make and save gifti image
    if group=='nanmean':
        gii_img = flatmap.make_func_gifti(data=surf_data, column_names=column_names)
        out_name = 'func'
    elif group=='mode':
        gii_img = flatmap.make_label_gifti(data=surf_data, label_names=label_names, column_names=column_names, label_RGBA=label_RGBA)
        out_name = 'label'
    if gifti:
        nib.save(gii_img, fpath + f'.{out_name}.gii')
    
    return gii_img

def weight_maps(
        model_name, 
        cortex, 
        train_exp,
        save=True
        ):
    """Get weights for trained models. 

    Optionally save out weight maps for cortex and cerebellum separately

    Args: 
        model_name (str): model_name (folder in conn_train_dir)
        cortex (str): cortex model name (example: tesselsWB162)
        train_exp (str): 'sc1' or 'sc2'
    Returns: 
        weights (n-dim np array); saves out cortex and cerebellar maps if `save` is True
    """
    # set directory
    dirs = const.Dirs(exp_name=train_exp)
    fpath = os.path.join(dirs.conn_train_dir, model_name)

    # get trained subject models
    model_fnames = glob.glob(os.path.join(fpath, '*.h5'))

    cereb_weights_all = []; cortex_weights_all = []; weights_all = []
    for model_fname in model_fnames:

        # read model data
        data = cio.read_hdf5(model_fname)
        
        # append cerebellar and cortical weights
        cereb_weights_all.append(np.nanmean(data.coef_, axis=1))
        cortex_weights_all.append(np.nanmean(data.coef_, axis=0))
        weights_all.append(data.coef_)
    
    # stack the weights
    weights_all = np.stack(weights_all, axis=0)

    # save cortex and cerebellum weight maps to disk
    if save:
        save_maps_cerebellum(data=np.stack(cereb_weights_all, axis=0), fpath=os.path.join(fpath, 'group_weights_cerebellum'))

        cortex_weights_all = np.stack(cortex_weights_all, axis=0)
        func_giis, hem_names = cdata.convert_cortex_to_gifti(data=np.nanmean(cortex_weights_all, axis=0), atlas=cortex)
        for (func_gii, hem) in zip(func_giis, hem_names):
            nib.save(func_gii, os.path.join(fpath, f'group_weights_cortex.{hem}.func.gii'))
        print('saving cortical and cerebellar weights to disk')
    
    return weights_all

def lasso_maps_cerebellum(
    model_name, 
    train_exp,
    weights='positive'
    ):
    """save lasso maps for cerebellum (count number of non-zero cortical coef)

    Args:
        model_name (str): full name of trained model
        train_exp (str): 'sc1' or 'sc2'
        weights (str): 'positive' or 'absolute' (neg. & pos.). default is 'positive'
    """
    # set directory
    dirs = const.Dirs(exp_name=train_exp)

    # get model path
    fpath = os.path.join(dirs.conn_train_dir, model_name)

    # get trained subject models
    model_fnames = glob.glob(os.path.join(fpath, '*.h5'))

    for stat in ['count', 'percent']:
        cereb_lasso_all = []
        for model_fname in model_fnames:

            # read model data
            data = cio.read_hdf5(model_fname)

            if weights=='positive':
                data.coef_[data.coef_ <= 0] = np.nan
            elif weights=='absolute':
                data.coef_[data.coef_ == 0] = np.nan
            
            # count number of non-zero weights
            data_nonzero = np.count_nonzero(~np.isnan(data.coef_,), axis=1)

            if stat=='count':
                pass # do nothing
            elif stat=='percent':
                num_regs = data.coef_.shape[1]
                data_nonzero = np.divide(data_nonzero,  num_regs)*100
            cereb_lasso_all.append(data_nonzero)

        # save maps to disk for cerebellum
        save_maps_cerebellum(data=np.stack(cereb_lasso_all, axis=0), 
                        fpath=os.path.join(fpath, f'group_lasso_{stat}_{weights}_cerebellum'))

def threshold_weights(data, threshold):
    """threshold data (2d np array) taking top `threshold` % of strongest weights

    Args: 
        data (np array): weight matrix; shape n_cerebellar_regs x n_cortical_regs
        threshold (int): if threshold=5, takes top 5% of strongest weights

    Returns:
        data (np array); same shape as input. NaN replaces all weights below threshold
    """
    num_vert = data.shape[1]

    thresh_regs = round(num_vert*(threshold*.01))
    sorted_roi = np.argsort(-data, axis=1)
    sorted_idx = sorted_roi[:,thresh_regs:]
    np.put_along_axis(data, sorted_idx, np.nan, axis=1)

    return data

def average_region_data(
    subjs,
    exp='sc1',
    cortex='tessels1002',
    atlas='MDTB10',
    method='ridge',
    alpha=8,
    weights='nonzero',
    average_subjs=True
    ):
    """average betas across `atlas`

    Args: 
        subjs (list of subjs): 
        exp (str): default is 'sc1'. other option: 'sc2'
        cortex (str): cortical atlas. default is 'tessels1002'
        atlas (str): cerebellar atlas. default is 'MDTB10'
        method (str): default is 'ridge'
        alpha (int): default is 8
        weights (str): default is 'nonzero'. other option is 'positive'
        average_subjs (bool): average betas across subjs? default is True
    Returns:    
       roi_mean, reg_names, colors
    """
    # set directory
    dirs = const.Dirs(exp_name=exp)

    # fetch `atlas`
    cerebellum_nifti = os.path.join(dirs.cerebellar_atlases, 'king_2019', f'atl-{atlas}_space-SUIT_dseg.nii')
    cerebellum_gifti = os.path.join(dirs.cerebellar_atlases, 'king_2019', f'atl-{atlas}_dseg.label.gii')

    if not os.path.exists(cerebellum_nifti):
        atlas.fetch_king_2019(data='atl', data_dir=dirs.cerebellar_atlases)

    # Load and average region data (average all subjs)
    Ydata = cdata.Dataset(experiment=exp, roi="cerebellum_suit", subj_id=subjs) 
    Ydata.load()
    Xdata = cdata.Dataset(experiment=exp, roi=cortex, subj_id=subjs) # const.return_subjs)
    Xdata.load()
    
    if average_subjs:
        Ydata.average_subj()
        Xdata.average_subj()

    # Read MDTB atlas
    index = cdata.read_suit_nii(cerebellum_nifti)
    Y, _ = Ydata.get_data('sess', True)
    X, _ = Xdata.get_data('sess', True)
    Ym, reg = cdata.average_by_roi(Y,index)

    reg_names =nio.get_gifti_labels(cerebellum_gifti)[1:]
    colors,_,_ = nio.get_gifti_colors(cerebellum_gifti, ignore_0=True)

    # Fit Model to region-averaged data 
    if method=='lasso':
        model_name = 'Lasso'
    elif method=='ridge':
        model_name = 'L2regression'

    fit_roi = getattr(model, model_name)(**{'alpha': alpha})
    fit_roi.fit(X,Ym)
    roi_mean = fit_roi.coef_[1:]

    if weights=='positive':
        roi_mean[roi_mean <= 0] = np.nan
    elif weights=='nonzero':
        roi_mean[roi_mean == 0] = np.nan
    
    return roi_mean, reg_names, colors

def regions_cortex(
    roi_betas,
    reg_names,
    cortex, 
    threshold=5,
    ):
    """save lasso maps for cortex

    Args:
        roi_betas (np array):
        reg_names (list of str):
        cortex (str):
        threshold (int or None): default is 5 (top 5%)
    
    Returns: 
        giis (list of giftis; 'L', and 'R' hem)
    """
    # optionally threshold weights based on `threshold`
    roi_all = []
    for hem in ['L', 'R']:

        labels = csparse.get_labels_hemisphere(roi=cortex, hemisphere=hem)
        roi_mean_hem = roi_betas[:,labels]

        # optionally threshold data
        if threshold is not None:
            # optionally threshold weights based on `threshold` (separately for each hem)
            roi_mean_hem = threshold_weights(data=roi_mean_hem, threshold=threshold)
        roi_all.append(roi_mean_hem)

    data_all = []
    for dd in np.hstack(roi_all):
        gii, _ = cdata.convert_cortex_to_gifti(data=dd, atlas=cortex, column_names=reg_names, data_type='func', hem_names=['L', 'R'])
        data_all.append(gii[0].darrays[0].data)

    # save to file
    giis = []
    for hem in ['L', 'R']:
        giis.append(nio.make_func_gifti_cortex(np.stack(data_all).T, column_names=reg_names, anatomical_struct=hem))
    
    return giis

def distances_cortex(
    roi_betas,
    reg_names,
    colors,
    cortex, 
    threshold=5,
    metric='gmean'
    ):
    """save lasso maps for cortex

    Args:
        roi_betas (np array):
        reg_names (list of str):
        colors (np array):
        cortex (str):
        threshold (int or None): default is 5 (top 5%)
        metric (str): default is 'gmean'
    
    Returns: 
        dataframe (pd dataframe)
    """
    # get data
    num_cols, num_vert = roi_betas.shape

    # optionally threshold weights based on `threshold`
    data = {}
    roi_dist_all = []
    for hem in ['L', 'R']:

        labels = csparse.get_labels_hemisphere(roi=cortex, hemisphere=hem)
        roi_mean_hem = roi_betas[:,labels]

        # optionally threshold data
        if threshold is not None:
            # optionally threshold weights based on `threshold` (separately for each hem)
            roi_mean_hem = threshold_weights(data=roi_mean_hem, threshold=threshold)
        
        # distances
        roi_dist_all.append(csparse.calc_distances(coef=roi_mean_hem, roi=cortex, metric=metric, hem_names=[hem])[hem])
    
    data.update({f'distance': np.hstack(roi_dist_all), 'hem': np.hstack([np.repeat('L', num_cols), np.repeat('R', num_cols)])})
        
    # save to disk  
    df = pd.DataFrame(np.vstack([colors, colors]), columns=['R','G', 'B', 'A'])
    data.update({'labels': np.tile(reg_names, 2), 'threshold': np.repeat(threshold*.01, len(df))})
    dataframe = pd.concat([df, pd.DataFrame.from_dict(data)], axis=1)
    
    return dataframe

def best_weights(
    train_exp='sc1',
    method='L2regression',
    ):
    """Get group average model weights for best trained model

    Args: 
        train_exp (str): default is 'sc1'
        method (str): default is 'L2regression'
    Returns: 
        group_weights (n-dim np array)

    """
    # get best L2regression model
    # best_model, cortex = get_best_model(dataframe=None, train_exp=train_exp, method=method)
    models, cortex_names = get_best_models(train_exp='sc1', method=method)

    for (best_model, cortex) in zip(models, cortex_names):

        # get group weights for best model
        weights = weight_maps(model_name=best_model, 
                            cortex=cortex, 
                            train_exp=train_exp, 
                            save=False
                            )
        
        # get group average weights
        group_weights = np.nanmean(weights, axis=0)

        # save best weights to disk
        dirs = const.Dirs(exp_name=train_exp)
        outdir = os.path.join(dirs.conn_train_dir, 'best_weights')
        if not os.path.exists(outdir):
            os.makedirs(outdir)
        dd.io.save(os.path.join(outdir, f'{best_model}.h5'), {'weights': group_weights})
    
