import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import mode
import os

import connectivity.constants as const
from connectivity.data import Dataset
import connectivity.model as model
import connectivity.data as data
import connectivity.run as run
import connectivity.visualize as vis
import connectivity.figures as fig
import connectivity.io as cio
import connectivity.evaluation as eval
from SUITPy import flatmap
import itertools
import nibabel as nib
import h5py
import deepdish as dd
import seaborn as sns
from sklearn.model_selection import cross_val_score
import connectivity.nib_utils as nio


def getX_random(N=60,Q=80):
    """Generates an artificial data set using iid data for Cortex
    """
    X1 = np.random.normal(0,1,(N,Q))
    X2 = np.random.normal(0,1,(N,Q))
    return X1, X2

def getX_cortex(atlas='tessels0042',sub = 's02'):
    """Generates an artificial data set using real cortical data
    """
    Xdata = Dataset('sc1','glm7',atlas,sub)
    Xdata.load_mat() # Load from Matlab
    X1, INFO1 = Xdata.get_data(averaging="sess") # Get numpy
    # Get the test data set
    XTdata = Dataset('sc2','glm7',atlas,sub)
    XTdata.load_mat() # Load from Matlab
    X2, INFO2 = XTdata.get_data(averaging="sess") # Get numpy
    # z-standardize cortical regressors 
    X1 = X1 / np.sqrt(np.sum(X1 ** 2, 0) / X1.shape[0])
    X2 = X2 / np.sqrt(np.sum(X2 ** 2, 0) / X1.shape[0])
    X1 = np.nan_to_num(X1)
    X2 = np.nan_to_num(X2)
    # i1 = np.where(INFO1.sess==1)
    # i2 = np.where(INFO1.sess==2)
    # rel = np.sum(X1[i1,:]*X1[i2,:])/np.sqrt(np.sum(X1[i1,:]**2) * np.sum(X1[i2,:]**2))
    return X1,X2,INFO1,INFO2

def getW(P,Q,conn_type='one2one',sparse_prob=0.05):
    if conn_type=='one2one':
        k = np.int(np.ceil(P/Q))
        W = np.kron(np.ones((k,1)),np.eye(Q))
        W = W[0:P,:]
    elif conn_type=='sparse':
        W=np.random.choice([0,1],p=[1-sparse_prob,sparse_prob],size=(P,Q))
    elif conn_type=='normal':
        W=np.random.normal(0,0.2,(P,Q))
    return W


def gridsearch(modelclass,log_alpha,X,Y):
    r_cv = np.empty((len(log_alpha),))
    for i,a in enumerate(log_alpha):
        model = modelclass(alpha=np.exp(a))
        a = cross_val_score(model, X, Y, scoring=eval.calculate_R_cv, cv=4)
        r_cv[i] = a.mean()
    indx = r_cv.argmax()
    return log_alpha[indx],r_cv

def sim_random(N=60,Q=80,P=1000,sigma=0.1,conn_type='one2one'):
    #  alphaR = validate_hyper(X,Y,model.L2regression)
    D=pd.DataFrame()
    X1,X2 = getX_random(N,Q)
    W = getW(P,Q,conn_type)
    Y1  = X1 @ W.T + np.random.normal(0,sigma,(N,P))
    Y1a = X1 @ W.T + np.random.normal(0,sigma,(N,P)) # Within sample replication
    Y2 = X2 @ W.T  + np.random.normal(0,sigma,(N,P)) # Out of sample

    # Tune hyper parameters for Ridge and Lasso model
    logalpha_ridge, r_cv_r = gridsearch(model.L2regression,[-4,-2,0,2,4,6,8,10],X1,Y1)
    logalpha_lasso, r_cv_l = gridsearch(model.Lasso,[-4,-3,-2,-1,0,1],X1,Y1)

    MOD =[]
    MOD.append(model.L2regression(alpha=np.exp(logalpha_ridge)))
    MOD.append(model.Lasso(alpha=np.exp(logalpha_lasso)))
    MOD.append(model.WTA_OLD())
    MOD.append(model.WTA())
    model_name = ['ridge','lasso','WTA_old','WTA']
    logalpha  = [logalpha_ridge,logalpha_lasso,np.nan,np.nan]

    for m in range(len(MOD)):

        MOD[m].fit(X1,Y1)
        Ypred1 = MOD[m].predict(X1)
        Ypred2 = MOD[m].predict(X2)
        r1,_ = eval.calculate_R(Y1a,Ypred1)
        r2,_ = eval.calculate_R(Y2,Ypred2)
        T=pd.DataFrame({'conn_type':[conn_type],
                    'model':[model_name[m]],
                    'modelNum':[m],
                    'numtessels':[Q],
                    'logalpha':[logalpha[m]],
                    'Rin':[r1],
                    'Rout':[r2]})
        D=pd.concat([D,T])
    return D


def sim_cortical(P=2000,atlas='tessels0042',sub = 's02',
                sigma=0.1,conn_type='one2one'):
    #  alphaR = validate_hyper(X,Y,model.L2regression)
    D=pd.DataFrame()
    X1,X2,I1,I2 = getX_cortex(atlas,sub)
    N1,Q = X1.shape
    N2,_ = X2.shape
    W = getW(P,Q,conn_type)
    Y1  = X1 @ W.T + np.random.normal(0,sigma,(N1,P))
    Y1a = X1 @ W.T + np.random.normal(0,sigma,(N1,P)) # Within sample replication
    Y2 = X2 @ W.T  + np.random.normal(0,sigma,(N2,P)) # Out of sample

    # Tune hyper parameters for Ridge and Lasso model
    logalpha_ridge, r_cv_r = gridsearch(model.L2regression,[-4,-2,0,2,4,6,8,10],X1,Y1)
    logalpha_lasso, r_cv_l = gridsearch(model.Lasso,[-3,-2,-1,0,1],X1,Y1)

    MOD =[]
    MOD.append(model.L2regression(alpha=np.exp(logalpha_ridge)))
    MOD.append(model.Lasso(alpha=np.exp(logalpha_lasso)))
    MOD.append(model.WTA_OLD())
    MOD.append(model.WTA())
    model_name = ['ridge','lasso','WTA_old','WTA']
    logalpha  = [logalpha_ridge,logalpha_lasso,np.nan,np.nan]

    for m in range(len(MOD)):

        MOD[m].fit(X1,Y1)
        Ypred1 = MOD[m].predict(X1)
        Ypred2 = MOD[m].predict(X2)
        r1,_ = eval.calculate_R(Y1a,Ypred1)
        r2,_ = eval.calculate_R(Y2,Ypred2)
        T=pd.DataFrame({'conn_type':[conn_type],
                    'model':[model_name[m]],
                    'modelNum':[m],
                    'numtessels':[Q],
                    'atlas':[atlas],
                    'sub':[sub],
                    'logalpha':[logalpha[m]],
                    'Rin':[r1],
                    'Rout':[r2]})
        D=pd.concat([D,T])
    return D

def sim_scenario1(): 
    conn_type=['one2one','sparse','normal']
    sigma = [1.4,2.0,1.2]
    D=pd.DataFrame()
    Q =[7,40,80,160,240]
    for i,ct in enumerate(conn_type):
        for q in Q:
            print(f"{ct} for {q}")
            T = sim_random(Q=q,sigma=sigma[i],conn_type=ct)
            D=pd.concat([D,T],ignore_index=True)
    D.to_csv('simulation_iid.csv')
    return D 

def sim_scenario2(): 
    conn_type=['one2one','sparse','normal']
    atlas = ['tessels0042','tessels0162','tessels0362','tessels0642','tessels1002']
    atlas = ['tessels0162']
    sigma = [2.0,3.0,2.0]
    sn = const.return_subjs
    D=pd.DataFrame()
    for i,ct in enumerate(conn_type):
        for s in sn:
            for a in atlas:
                print(f"{ct} for {a} for {s}")
                T = sim_cortical(sigma=sigma[i],conn_type=ct,atlas=a,sub=s)
                D=pd.concat([D,T],ignore_index=True)
    D.to_csv('simulation_cortex_0162.csv')
    return D 

def plot_scaling(atlas='tessels0162', exp='sc1'): 
    for i,s in enumerate(const.return_subjs):
        Xdata = Dataset(exp,'glm7',atlas,s)
        Xdata.load_mat() # Load from Matlab
        X, INFO1 = Xdata.get_data(averaging="sess") # Get numpy
        Q = X.shape[1]
        if i ==0:
            std=np.empty((24,Q))
        std[i,:] = np.sqrt(np.sum(X ** 2, 0) / X.shape[0])
    
    gii,name = data.convert_cortex_to_gifti(std.mean(axis=0),atlas=atlas)
    nio.view_cortex(gii[0],hemisphere='L')

def sim_cortex_differences(P=2000,atlas='tessels0162',
                    sigma=2.0,conn_type='one2one'):
    #  alphaR = validate_hyper(X,Y,model.L2regression)
    D=pd.DataFrame()
    for i,s in enumerate(const.return_subjs):
        X1,X2,I1,I2 = getX_cortex(atlas,s)
        N1,Q = X1.shape
        N2,_ = X2.shape
        W = getW(P,Q,conn_type)
        Y1  = X1 @ W.T + np.random.normal(0,sigma,(N1,P))

        MOD =[]; 
        MOD.append(model.L2regression(alpha=np.exp(3)))
        MOD.append(model.Lasso(alpha=np.exp(-1)))

        for m in range(len(MOD)):
            MOD[m].fit(X1,Y1)
        if i ==0:
            correct=np.empty((24,Q))
            area=np.empty((24,Q))
            
        numsim=W.sum(axis=0) # Simulations per cortical parcels 
        conn = W.T @ (np.abs(MOD[1].coef_)>0)
        correct[i,:] = np.diag(conn)/numsim 
        area[i,:] = conn.sum(axis=1)/numsim
    
    
    gii,name = data.convert_cortex_to_gifti(area.mean(axis=0),atlas=atlas)
    nio.view_cortex(gii[0],hemisphere='L')
    pass



if __name__ == "__main__":
    sim_cortex_differences()