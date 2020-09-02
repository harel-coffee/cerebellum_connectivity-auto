from pathlib import Path
import os


class Defaults:

    def __init__(self):
        self.return_subjs = [2,3,4,6,8,9,10,12,14,15,17,18,19,20,21,22,24,25,26,27,28,29,30,31]
        # self.conn_file = 'sc1_sc2_taskConds_conn.txt'
        self.conn_file = 'tasks.json'
        self.config_file = 'config.json'

class Dirs: 

    def __init__(self, study_name='sc1', glm=7):
        self.BASE_DIR = Path(__file__).absolute().parent.parent / 'data'
        self.DATA_DIR = self.BASE_DIR / study_name
        self.BEHAV_DIR = self.DATA_DIR / 'data'
        self.IMAGING_DIR = self.DATA_DIR / 'imaging_data'
        self.SUIT_DIR = self.DATA_DIR / 'suit'
        self.REG_DIR = self.DATA_DIR / 'RegionOfInterest'
        self.GLM_DIR = self.DATA_DIR / f'GLM_firstlevel_{glm}'
        self.ENCODE_DIR = self.DATA_DIR / 'encoding' / f'glm{glm}'
        self.BETA_REG_DIR = self.DATA_DIR / 'beta_roi' / f'glm{glm}'
        self.CONN_DIR = self.DATA_DIR / 'conn_models' / f'glm{glm}'
        self.CONN_TRAIN_DIR = self.CONN_DIR / 'train'
        self.CONN_EVAL_DIR = self.CONN_DIR / 'eval'

        # create folders if they don't already exist
        fpaths = [self.BETA_REG_DIR, self.CONN_TRAIN_DIR, self.CONN_EVAL_DIR]
        for fpath in fpaths:
            if not os.path.exists(fpath):
                print(f'creating {fpath} although this dir should already exist, check your folder transfer!')
                os.makedirs(fpath)