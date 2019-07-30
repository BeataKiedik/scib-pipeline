import scanpy as sc
import pandas as pd
import seaborn as sns
import sklearn.metrics as scm
from scIB.utils import *
import cProfile
from pstats import Stats
from memory_profiler import profile
import memory_profiler
import scIB
import timeit
import numpy as np

sns.set_context('talk')
sns.set_palette('Dark2')

### Silhouette score
def silhouette_score(adata, batch='method', group='cell_ontology_class', metric='euclidean', embed='X_pca'):
    """
    Silhouette score subsetted for each cluster (group) between batches.
    This results in 1 score per group label
    params:
        adata: 
        batch: batches to be compared against
        group: group labels to be subsetted by e.g. cell type
        metric: 
        embed: name of column in adata.obsm
    returns:
        per_group: scores per group label
        sil_means: mean silhouette score of group means
    """
    checkAdata(adata)
    if embed not in adata.obsm:
        raise KeyError(f'{embed} not in obsm')
    
    # ony look at group labels that are present for all batches
    n_batch = adata.obs[batch].nunique()
    labels = adata.obs.groupby(group)[batch].nunique()
    labels = labels[labels == n_batch]
    
    sil_means = []
    per_group = []
    for j in labels.index:
        tmp_type = adata[adata.obs[group] == j]
        sil = scm.silhouette_score(tmp_type.obsm[embed], tmp_type.obs[batch], metric=metric)
        sil_means.append(sil)
        per_group.extend(scm.silhouette_samples(tmp_type.obsm[embed], tmp_type.obs[batch], metric=metric))
    print(f'mean silhouette over label means: {np.mean(sil_means)}')
    per_group = [abs(i) for i in per_group] # take only absolute value
    print(f'mean silhouette per cell: {np.mean(per_group)}')
    
    return per_group, sil_means

def plot_silhouette_score(adata_dict):
    """
    params:
        adata_dict: dictionary of adata objects, each labeled by e.g. integration method name
    """
    for label, adata in adata_dict.items():
        checkAdata(adata)
        per_group, sil_means = silhouette_score(adata)
        sns.distplot(per_group, label=label, hist=False)

### Naive cluster overlap
def cluster_overlap(adata, group1='louvain', group2='louvain_post'):
    checkAdata(adata)
    cluster_ov = {}
    louv_post_sizes = adata.obs.groupby(group1).size()
    for i in adata.obs[group2].cat.categories:
        a = adata.obs[adata.obs[group2] == i]
        overlap = a.groupby(group1).size()
        cluster_ov[i] = (overlap / louv_post_sizes).sum() / len(overlap[overlap > 0])
    return cluster_ov

def plot_cluster_overlap(adata_dict, group1='louvain', group2='louvain_post'):
    """
    params:
        adata_dict: dictionary of adata objects, each labeled by e.g. integration method name
        group1: 
        group2: 
    return:
        clust_df: dataframe with plotted data points
    """
    series = []
    method_names = list(adata_dict.keys())
    for i in method_names:
        c_ov = cluster_overlap(adata[i], group1=group1, group2=group2)
        series.append(pd.Series(c_ov))
    clust_df = pd.DataFrame(series).transpose()

    clust_df.columns = method_names
    sns.boxplot(data=clust_df)
    sns.swarmplot(data=clust_df, color=".25")
    
    return clust_df

### NMI
def nmi(adata, group1, group2, onmi_dir="../../Overlapping-NMI/"):
    group1_file = write_tmp_labels(adata, group1)
    group2_file = write_tmp_labels(adata, group2)
    
    nmi_call = subprocess.Popen(
        [onmi_dir+"onmi", group1_file, group2_file], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT)
    
    stdout, stderr = nmi_call.communicate()
    print(stderr)
    nmi_out = stdout.decode()
    print(nmi_out)
    
    nmi_split = [x.strip().split('\t') for x in nmi_out.split('\n')]
    nmi_max = nmi_split[0][1]
    
    # remove temporary files
    os.remove(group1_file)
    os.remove(group2_file)
    
    return nmi_max

def measureTM(*args, **kwargs, info=False):
    prof = cProfile.Profile()
    out = memory_profiler.memory_usage((prof.runcall, args, kwargs), retval=True) 
    mem = np.max(out[0])- out[0][0]
    if info:
        print(f'memory usage:{round(mem,0) } MB')
        print(f'runtime: {round(Stats(prof).total_tt,0)} s')
    return mem, Stats(prof).total_tt, out[1:]