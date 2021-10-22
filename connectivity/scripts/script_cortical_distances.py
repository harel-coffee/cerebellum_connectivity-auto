from collections import defaultdict
import click
import os
import pandas as pd
import nibabel as nib
import numpy as np
import deepdish as dd

from connectivity import weights as cweights
from connectivity import visualize as summary
import connectivity.constants as const

# @click.command()
# @click.option("--roi")
# @click.option("--weights")
# @click.option("--data_type")

def distances_summary(
    atlas='MDTB10', 
    weights='nonzero', 
    method='ridge', # L2regression
    thresholds=[1,5],
    metric='gmean',
    exp='sc1',
    ):

    dirs = const.Dirs(exp_name=exp)
    subjs, _ = cweights.split_subjects(const.return_subjs, test_size=0.3)

    # models, cortex_names = summary.get_best_models(method=method) 
    cortex = 'tessels1002'; models = [f'{method}_{cortex}_alpha_8']; cortex_names = ['tessels1002']

    data_dict_all = defaultdict(list)
    for (best_model, cortex) in zip(models, cortex_names):

        # get alpha for each model
        alpha = int(best_model.split('_')[-1])
        for threshold in thresholds:
            for subj in subjs:
                roi_betas, reg_names, colors = cweights.average_region_data(subj,
                                        exp=exp, cortex=cortex, 
                                        atlas=atlas, method=method, alpha=alpha, 
                                        weights=weights, average_subjs=False)

                # save out cortical distances
                data_dict = cweights.distances_cortex(roi_betas, reg_names, colors, 
                            cortex=cortex, threshold=threshold, metric=metric)
                data_dict.update({'subj': np.repeat(subj, len(reg_names)*2)})

                for k, v in data_dict.items():
                    data_dict_all[k].extend(v)

    # save dataframe to disk
    df = pd.DataFrame.from_dict(data_dict_all) 
    fpath = os.path.join(dirs.conn_train_dir, 'cortical_distances_stats.csv')  
    if os.path.isfile(fpath):
        df_exist = pd.read_csv(fpath) 
        df = pd.concat([df_exist, df])
    df.to_csv(fpath)
        
def distances_map(
    atlas='MDTB10', 
    method='ridge', 
    weights='nonzero',
    threshold=100
    ):

    exp = 'sc1'
    dirs = const.Dirs(exp_name=exp)

    subjs, _ = cweights.split_subjects(const.return_subjs, test_size=0.3)

    # models, cortex_names = summary.get_best_models(method=method) 
    cortex = 'tessels1002'
    models = [f'{method}_{cortex}_alpha_8']
    cortex_names = ['tessels1002']

    for (best_model, cortex) in zip(models, cortex_names):
        
        # full path to best model
        fpath = os.path.join(dirs.conn_train_dir, best_model)
        if not os.path.exists(fpath):
            os.makedirs(fpath)

        # get alpha for each model
        alpha = int(best_model.split('_')[-1])
        roi_betas_all = []
        for subj in subjs:
            roi_betas, reg_names, colors = cweights.average_region_data(subj,
                                    exp=exp, cortex=cortex, 
                                    atlas=atlas, method=method, alpha=alpha, 
                                    weights=weights, average_subjs=False)
                                    
            roi_betas_all.append(roi_betas)

        roi_betas_group = np.nanmean(np.stack(roi_betas_all), axis=0)
        giis = cweights.regions_cortex(roi_betas_group, reg_names, cortex=cortex, threshold=threshold)
            
        fname = f'group_{atlas}_threshold_{threshold}'
        [nib.save(gii, os.path.join(fpath, f'{fname}.{hem}.func.gii')) for (gii, hem) in zip(giis, ['L', 'R'])]

def run():
    distances_summary()
    distances_map()

# if __name__ == "__main__":
#     run()