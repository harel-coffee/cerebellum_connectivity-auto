from collections import defaultdict
import click
import os
import pandas as pd
import nibabel as nib
import numpy as np
import deepdish as dd
import matplotlib.pyplot as plt
import seaborn as sns 
import scipy.stats as ss 

from connectivity import weights as cweights
from connectivity import visualize as summary
from connectivity import data as cdata
import connectivity.constants as const

from sklearn.decomposition import dict_learning, sparse_encode
import numpy as np

def random_V(K=5,N=20):
    V = np.random.normal(0,1,(K,N))
    V = V - V.mean(axis=1).reshape(-1,1)
    V = V / np.sqrt(np.sum(V**2,axis=1).reshape(-1,1))
    return V

def random_U(P=100,K=5,type='onegamma',alpha=2,beta=0.3):
    if type=='onegamma':
        u = np.random.choice(K,(P,))
        g = np.random.gamma(alpha,beta,(P,))
        U = np.zeros((P,K))
        for i in np.arange(K):
            U[u==i,i] = g[u==i]
    elif type=='iidgamma':
        U = np.random.gamma(alpha,beta,(P,K))
    elif type=='one':
        u = np.random.choice(K,(P,))
        U = np.zeros((P,K))
        for i in np.arange(K):
            U[u==i, i] = 1
    return U

def random_Y(U,V,eps=1):
    N = V.shape[1]
    P = U.shape[0]
    Y = U @ V + np.random.normal(0,eps/np.sqrt(N),(P,N))
    return Y

def check_consistency(P=100,K=5,N=40):
    num=10
    U = random_U(P,K,'iidgamma')
    V = random_V(K,N)
    Y = random_Y(U,V,eps=3)
    Uhat = np.empty((num,P,K))
    Vhat = np.empty((num,K,N))
    iter = np.empty((num,))
    loss = np.empty((num,))

    for i in range(num):
        # Determine random starting value
        V_init = random_V(K,N)
        U_init = np.random.uniform(0,1,(P,N))
        Uhat[i,:,:],Vhat[i,:,:],errors,iter[i] = dict_learning (Y,alpha = 0.1, n_components=K,
            method='cd',positive_code=True,
            code_init=U_init, dict_init=V_init,
            return_n_iter=True,max_iter=200)
        loss[i] = errors[-1]
    i = np.argsort(loss)
    loss = loss[i]
    iter = iter[i]
    Vhat = Vhat[i,:,:]
    _,M = vmatch(Vhat,Vhat)
    plt.imshow(M)
    pass

def dict_learn_rep(Y,K=5,num=1):
    num_subj,P,N = Y.shape
    Vsubj = np.empty((num_subj,K,N))
    Vhat = np.empty((num,K,N))
    iter = np.empty((num,))
    loss = np.empty((num,))
    for s in range(num_subj):
        print(f"subj:{s}")
        Vhat = np.empty((num,K,N))
        for i in range(num):
            # Determine random starting value
            V_init = random_V(K,N)
            U_init = np.random.uniform(0,1,(P,N))
            Uhat,Vhat[i,:,:],errors,iter[i] = dict_learning(Y[s,:,:],alpha = 0.1, n_components=K,
            method='cd',positive_code=True,
            code_init=U_init, dict_init=V_init,
            return_n_iter=True,max_iter=200)
            loss[i] = errors[-1]
        # Sort the solutions by the loss
        i=loss.argmin()
        Vsubj[s,:,:] = Vhat[i,:,:]
    return Vsubj

def vmatch(V1,V2):
    """Gets the mean minimal distances of every vector in V1
        to any vector in V2.
    """
    num_sub,K1,N = V1.shape
    num_sub,K2,N = V2.shape
    M = np.zeros((num_sub,num_sub)) # Mean correspondence
    for i in range(num_sub):
        for j in range(num_sub):
            if i==j:
                M[i,j]=np.nan
            else:
                M[i,j]=(V1[i,:,:] @ V2[j,:,:].T).max(axis=1).mean()
    return np.nanmean(M,axis=1), M


def vmatch_baseline(K=[5,5],N=30,num=20):
    V = np.empty((2,),'object')
    for set in range(2):
        V[set]=np.empty((num,K[set],N))
        for i in range(num):
            V[set][i,:,:]=random_V(K[set],N)
    vm,M = vmatch(V[0],V[1])
    return np.mean(vm)

def vmatch_baseline_fK():
    kmax= 30
    vm = np.empty((kmax,))
    kk = np.arange(1,kmax+1)
    for k in kk:
        vm[k-1] = vmatch_baseline([10,k],60)
    plt.plot(kk,vm)
    pass

def demean_data(D,T): 
    m = D[T.split=="common",:].mean(axis=0)
    D = D-m
    return D

def get_decomponsition(roi="cerebellum_suit", sn="s02", K=17,num = 5):
    data = cdata.Dataset(experiment="sc1",glm="glm7",roi=roi,subj_id=sn)
    data.load_mat()
    T = data.get_info()
    D1,T1 = data.get_data(averaging="exp", weighting=False, subset=T.inst==0)
    data = cdata.Dataset(experiment="sc2",glm="glm7",roi=roi,subj_id=sn)
    data.load_mat()
    T = data.get_info()
    D2,T2 = data.get_data(averaging="exp", weighting=False, subset=T.inst==0)
    
    # Align the two data sets 
    D1 = demean_data(D1,T1)
    D2 = demean_data(D2,T2)
    D = np.concatenate([D1,D2],axis=0)
    Y = D - np.mean(D,axis=0)
    T = pd.concat([T1,T2])
    Y=Y.T
    pass

    P,N = Y.shape
    Vhat = np.empty((num,K,N))
    iter = np.empty((num,))
    loss = np.empty((num,))
    for i in range(num):
        print(i)
        # Determine random starting value
        V_init = random_V(K,N)
        U_init = np.random.uniform(0,1,(P,K))
        Uhat,Vhat[i,:,:],errors,iter[i] = dict_learning(Y,alpha = 0.1, n_components=K, method='cd',positive_code=True, code_init=U_init, dict_init=V_init, return_n_iter=True,max_iter=200)
        loss[i] = errors[-1]
        # Sort the solutions by the loss
    i=np.argsort(loss)
    loss = loss[i]
    iter = iter[i]
    Vhat = Vhat[i,:,:]
    _,M = vmatch(Vhat,Vhat)
    d = {'loss':loss,'iter':iter,'Vhat':Vhat,'M':M}
    return d

def do_all_decomposition(roi="cerebellum_suit", K=10,num = 5):
    num_subj = len(const.return_subjs)
    d = []
    for i,sn in enumerate(const.return_subjs[21:]):
        filename=const.base_dir / "sc1" / "conn_models" / "dict_learn" / f"decomp_{roi}_{sn}_{K}.h5"
        d.append(get_decomponsition(roi=roi, sn=sn, K=K,num = num))
        dd.io.save(filename,d[-1])
    return d

def load_decomposition(roi=["cerebellum_suit"],K=[10],subjs=const.return_subjs):
    """Loads the decomposition from disk
    """
    num_subj = len(subjs)
    Vhat = np.empty((len(roi),),object)
    D = pd.DataFrame()
    d = pd.DataFrame()
    for r in range(len(roi)):
        Vhat[r]=np.empty((num_subj,K[r],61))
        for i,sn in enumerate(subjs):
            filename=const.base_dir / "sc1" / "conn_models" / "dict_learn" / f"decomp_{roi[r]}_{sn}_{K[r]}.h5"
            di= dd.io.load(filename)
            Vhat[r][i,:,:]=di['Vhat'][0,:,:]
            d['subjn'] = [sn]
            d['sn'] = [i]
            d['rname'] = [roi[r]]
            d['rn'] = [r]
            d['K'] = [K[r]]
            d['match_self'] = [np.nanmean(di['M'])]
            D= pd.concat([D,d],ignore_index=True)
    return Vhat,D

def check_alignment(roi=["cerebellum_suit","tessels1002"],K=[10,10]):
    # Load all the the desired decompositions 
    Vhat,D = load_decomposition(roi,K)
    # Now compare the different values
    _,M00 = vmatch(Vhat[0],Vhat[0])
    _,M11 = vmatch(Vhat[1],Vhat[1])
    _,M01 = vmatch(Vhat[0],Vhat[1])
    _,M10 = vmatch(Vhat[1],Vhat[0])
    D['same_roi']= np.concatenate([np.nanmean(M00,axis=1),np.nanmean(M11,axis=1)])
    D['diff_roi']= np.concatenate([np.nanmean(M01,axis=1),np.nanmean(M10,axis=1)])
    E=pd.melt(D,id_vars=['subjn','sn','rn','rname','K'],value_vars=['same_roi','diff_roi'],var_name='match',value_name='corr')
    sns.barplot(data=E,x='rn',y='corr',hue='match')
    for i in range(2):
        t,p = ss.ttest_rel(D[D.rn==i].same_roi,D[D.rn==i].diff_roi)
        print(f"region: {roi[i]} t:{t:.3} p:{p:.3}")
    pass

def get_average_data_by_region(): 
    roi = 'cerebellum_suit'
    data = cdata.Dataset(experiment="sc1",glm="glm7",roi=roi,subj_id='all')
    data.load_h5()
    T = data.get_info()
    D1,T1 = data.get_data(averaging="exp", weighting=False, subset=T.inst==0)
    data = cdata.Dataset(experiment="sc2",glm="glm7",roi=roi,subj_id='all')
    data.load_h5()
    T = data.get_info()
    D2,T2 = data.get_data(averaging="exp", weighting=False, subset=T.inst==0)
    
    # Align the two data sets 
    D1 = demean_data(D1,T1)
    D2 = demean_data(D2,T2)
    D = np.concatenate([D1,D2],axis=0)
    Y = D - np.mean(D,axis=0)
    T = pd.concat([T1,T2])

    # get regions of interest definition 
    atlas = const.base_dir / "cerebellar_atlases" / "king_2019" / "atl-MDTB10_space-SUIT_dseg.nii"
    R = cdata.read_suit_nii(atlas)
    
    Ym,regNum = cdata.average_by_roi(Y,R)
    return Ym, regNum

def calc_alignment_by_region(): 
    """Determines alignment of functional vectors by region
    """
    # Get cerebellar data per region     
    Ym,regNum = get_average_data_by_region()
    Ym = Ym[:,1:]
    Ym = Ym / np.sqrt(np.sum(Ym**2,axis=0))
    
    # Get comparision vectos 
    Vhat,D = load_decomposition(['cerebellum_suit','tessels1002','tessels1002'],[10,10,17])
    N = D.shape[0]
    K = Ym.shape[1]
    match = np.zeros((N,K))
    for i,d in D.iterrows():
        A = Ym.T @ Vhat[d.rn][d.sn,:,:].T
        match[i,:]=A.max(axis=1)
    # V = Ym.T @ Ym 
    R = pd.DataFrame()
    for i in range(K):
        D['match']=match[:,i]
        D['MDTBRegion']=np.ones((N,1))*(i+1)
        R= pd.concat([R,D],ignore_index=True)
    sns.lineplot(data=R,x="MDTBRegion",y="match",hue='rn',palette=plt.get_cmap('tab10'))
    plt.legend(labels=["Cerebellum 10","Cortex 10","Cortex 17"])
    pass


if __name__ == '__main__':
    # M = vmatch_baseline([17,17],N=62)
    # correspondence_sim()
    # d = do_all_decomposition(roi="tessels1002",K=17,num=5)
    # check_alignment(roi=["cerebellum_suit","tessels1002"],K=[10,10])
    # vmatch_baseline_fK()
    calc_alignment_by_region()
    pass