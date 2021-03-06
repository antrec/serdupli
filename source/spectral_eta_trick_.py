#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Attempts to minimize \sum_{ij} A_{ij} |pi_i - pi_j| with eta-trick and spectral
ordering
"""
import warnings
import sys
import numpy as np
from scipy.sparse import issparse, coo_matrix, lil_matrix, find
from scipy.linalg import toeplitz
from mdso import SpectralBaseline
import matplotlib.pyplot as plt
from mdso.spectral_embedding_ import spectral_embedding


def p_sum_score(X, p=1, permut=None, normalize=False):
    """ computes the p-sum score of X or X[permut, :][:, permut] if permutation
    provided
    """
    if issparse(X):
        if not isinstance(X, coo_matrix):
            X = coo_matrix(X)

        r, c, v = X.row, X.col, X.data

        if permut is not None:
            d2diag = abs(permut[r] - permut[c])
        else:
            d2diag = abs(r - c)

        if p != 1:
            d2diag **= p

        prod = np.multiply(v, d2diag)
        score = np.sum(prod)

    else:
        if permut is not None:
            X_p = X.copy()[permut, :]
            X_p = X_p.T[permut, :].T
        else:
            X_p = X

        n = X_p.shape[0]
        d2diagv = np.arange(n)
        if p != 1:
            d2diagv **= p
        D2diag_mat = toeplitz(d2diagv)
        prod = np.multiply(X_p, D2diag_mat)
        score = np.sum(prod)

    return score


def plot_mat(X, title='', permut=None):

    if permut is not None:
        if issparse(X):
            (iis, jjs, _) = find(X)
            pis = permut[iis]
            pjs = permut[jjs]
            # Xl = X.tolil(copy=True)
        else:
            Xl = X.copy()
            Xl = Xl[permut, :]
            Xl = Xl.T[permut, :].T

    fig = plt.figure(1)
    plt.gcf().clear()
    axes = fig.subplots(1, 2)
    # ax = fig.add_subplot(111)
    if issparse(X):
        if permut is None:
            (pis, pjs, _) = find(X)
        # cax = ax.plot(pis, pjs, 'o', mfc='none')
        axes[0].plot(pis, pjs, 'o', mfc='none')
    else:
        # cax = ax.matshow(Xl, interpolation='nearest')
        axes[0].matshow(Xl, interpolation='nearest')
    if permut is not None:
        axes[1].plot(np.arange(len(permut)), permut, 'o', mfc='none')
    # fig.colorbar(cax)
    plt.title(title)
    plt.draw()
    plt.pause(0.01)

    return


def spectral_eta_trick(X, n_iter=50, dh=1, score_function='1SUM', return_score=False,
                       do_plot=False, circular=False, norm_laplacian=None,
                       norm_adjacency=None, eigen_solver=None,
                       scale_embedding=False,
                       add_momentum=None):
    """
    Performs Spectral Eta-trick Algorithm from
    https://arxiv.org/pdf/1806.00664.pdf
    which calls several instances of the Spectral Ordering baseline (Atkins) to
    try to minimize 1-SUM or Huber-SUM (instead of 2-SUM)
    with the so-called eta-trick.
    """

    (n, n2) = X.shape
    assert(n == n2)

    spectral_algo = SpectralBaseline(circular=circular,
                                     norm_laplacian=norm_laplacian,
                                     norm_adjacency=norm_adjacency,
                                     eigen_solver=eigen_solver,
                                     scale_embedding=scale_embedding)

    best_perm = np.random.permutation(n)
    best_score = compute_score(X, score_function=score_function, dh=dh, perm=best_perm)
    # best_score = n**(p+2)

    if issparse(X):
        if not isinstance(X, coo_matrix):
            X = coo_matrix(X)

        r, c, v = X.row, X.col, X.data
        eta_vec = np.ones(len(v))
        # if add_momentum:
        #     eta_old = np.ones(len(v))

        for it in range(n_iter):

            X_w = X.copy()
            X_w.data /= eta_vec

            if add_momentum:
                eta_old = eta_vec

            new_perm = spectral_algo.fit_transform(X_w)
            if np.all(new_perm == best_perm):
                break
            # if new_perm[0] > new_perm[-1]:
            #     new_perm *= -1
            #     new_perm += (n-1)  # should it not be n-1 instead of n ?!

            # new_score = p_sum_score(X, permut=new_perm, p=p)
            new_score = compute_score(X, score_function=score_function, dh=dh, perm=new_perm)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            eta_vec = abs(p_inv[r] - p_inv[c])
            if circular:
                # pass
                eta_vec = np.minimum(eta_vec, n - eta_vec)
            eta_vec = np.maximum(dh, eta_vec)

            if add_momentum:
                eta_vec = (1-add_momentum) * eta_vec + add_momentum * eta_old

            if do_plot:
                title = "it %d, score: %1.5e" % (it, new_score)
                plot_mat(X, permut=new_perm, title=title)

    else:
        eta_mat = np.ones((n, n))

        for it in range(n_iter):

            X_w = np.divide(X, eta_mat)
            new_perm = spectral_algo.fit_transform(X_w)
            # if new_perm[0] > new_perm[-1]:
            #     new_perm *= -1
            #     new_perm += (n-1)
            if np.all(new_perm == best_perm):
                break

            # new_score = p_sum_score(X, permut=new_perm, p=p)
            new_score = compute_score(X, score_function=score_function, dh=dh, perm=new_perm)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            eta_mat = abs(np.tile(p_inv, n) - np.repeat(p_inv, n))
            if circular:
                # pass
                eta_mat = np.minimum(eta_mat, n - eta_mat)
            eta_mat = np.reshape(eta_mat, (n, n))
            eta_mat = np.maximum(dh, eta_mat)

            if do_plot:
                title = "it %d, score: %1.5e" % (it, new_score)
                plot_mat(X, permut=new_perm, title=title)

    if return_score:
        return(best_perm, best_score)
    else:
        return(best_perm)


def spectral_eta_trick2(X, n_iter=50, dh=1, p=1, return_score=False,
                       do_plot=False, circular=False, norm_laplacian=None,
                       norm_adjacency=None, eigen_solver=None,
                       scale_embedding=False,
                       add_momentum=None):
    """
    Performs Spectral Eta-trick Algorithm from
    https://arxiv.org/pdf/1806.00664.pdf
    which calls several instances of the Spectral Ordering baseline (Atkins) to
    try to minimize 1-SUM or Huber-SUM (instead of 2-SUM)
    with the so-called eta-trick.
    """

    (n, n2) = X.shape
    assert(n == n2)

    if n < 3:
        best_perm = np.arange(n)
        if return_score:
            return(best_perm, -1)
        else:
            return(best_perm)

    spectral_algo = SpectralBaseline(circular=circular,
                                     norm_laplacian=norm_laplacian,
                                     norm_adjacency=norm_adjacency,
                                     eigen_solver=eigen_solver,
                                     scale_embedding=scale_embedding)

    best_perm = np.arange(n)
    best_score = n**(p+2)

    if issparse(X):
        if not isinstance(X, coo_matrix):
            X = coo_matrix(X)

        r, c, v = X.row, X.col, X.data
        eta_vec = np.ones(len(v))
        if add_momentum:
            eta_old = np.ones(len(v))

        for it in range(n_iter):

            X_w = X.copy()
            X_w.data /= eta_vec

            embedding = spectral_embedding(X_w)
            new_perm = np.argsort(embedding[:, 0])

            # new_perm = spectral_algo.fit_transform(X_w)
            if np.all(new_perm == best_perm):
                break
            if new_perm[0] > new_perm[-1]:
                embedding = embedding[::-1, :]
                new_perm *= -1
                new_perm += (n-1)

            new_score = p_sum_score(X, permut=new_perm, p=p)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            # eta_vec = abs(p_inv[r] - p_inv[c])
            d_ = 3
            eta_vec = np.sum(abs(embedding[r, :d_] - embedding[c, :d_]), axis=1)
            # if circular:
            #     # pass
            #     eta_vec = np.minimum(eta_vec, n - eta_vec)
            # eta_vec = np.maximum(dh, eta_vec)

            if do_plot:
                title = "it %d, %d-SUM: %1.5e" % (it, p, new_score)
                plot_mat(X, permut=new_perm, title=title)

    else:
        eta_mat = np.ones((n, n))

        for it in range(n_iter):

            X_w = np.divide(X, eta_mat)
            embedding = spectral_embedding(X_w)
            new_perm = np.argsort(embedding[:, 0])

            # new_perm = spectral_algo.fit_transform(X_w)
            # if new_perm[0] > new_perm[-1]:
            #     embedding = embedding[::-1, :]
            #     new_perm *= -1
            #     new_perm += (n-1)
            # if np.all(new_perm == best_perm):
            #     break

            new_score = p_sum_score(X, permut=new_perm, p=p)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            d_ = 5
            d_ = min(n-1, d_)
            # eta_vec = np.sum(abs(embedding[r, :d_] - embedding[c, :d_]), axis=1)
            eta_mat = np.identity(n).flatten()
            for dim in range(d_):
                # eta_mat = eta_mat + abs(np.tile(embedding[:, dim], n) - np.repeat(embedding[:, dim], n))
                d_perm = np.argsort(embedding[:, dim])
                d_perm = (1./(1 + dim)) * np.argsort(d_perm)
                eta_mat = eta_mat + abs(np.tile(d_perm, n) - np.repeat(d_perm, n))

            # eta_mat = abs(np.tile(p_inv, n) - np.repeat(p_inv, n))
            # if circular:
            #     # pass
            #     eta_mat = np.minimum(eta_mat, n - eta_mat)
            eta_mat = np.reshape(eta_mat, (n, n))
            # eta_mat = np.maximum(dh, eta_mat)

            if do_plot:
                title = "it %d, %d-SUM: %1.5e" % (it, p, new_score)
                plot_mat(X, permut=new_perm, title=title)

    if return_score:
        return(best_perm, best_score)
    else:
        return(best_perm)


def compute_score(X, score_function='1SUM', dh=1, perm=None, circular=False):
    """ computes the p-sum score of X or X[perm, :][:, perm] if permutation
    provided
    """

    (n, _) = X.shape
    if issparse(X):
        if not isinstance(X, coo_matrix):
            X = coo_matrix(X)

        r, c, v = X.row, X.col, X.data

        if perm is not None:
            d2diag = abs(perm[r] - perm[c])
        else:
            d2diag = abs(r - c)

        if not isinstance(dh, int):
            dh = int(dh)

        if score_function == '2SUM':
            d2diag **= 2
        elif score_function == 'Huber':
            is_in_band = (d2diag <= dh)
            if circular:
                is_in_band += (d2diag >= n - dh)
            in_band = np.where(is_in_band)[0]
            out_band = np.where(~is_in_band)[0]
            d2diag[in_band] **= 2
            d2diag[out_band] *= 2 * dh
            d2diag[out_band] -= dh**2
        elif score_function == 'R2S':
            is_in_band = (d2diag <= dh)
            if circular:
                is_in_band += (d2diag >= n - dh)
            in_band = np.where(is_in_band)[0]
            out_band = np.where(~is_in_band)[0]
            d2diag[in_band] **= 2
            d2diag[out_band] = dh**2

        prod = np.multiply(v, d2diag)
        score = np.sum(prod)

    else:
        if perm is not None:
            X_p = X.copy()[perm, :]
            X_p = X_p.T[perm, :].T
        else:
            X_p = X

        n = X_p.shape[0]
        d2diagv = np.arange(n)
        if score_function == '2SUM':
            d2diagv **= 2
        elif score_function == 'Huber':
            is_in_band = (d2diagv <= dh)
            if circular:
                is_in_band += (d2diagv >= n - dh)
            in_band = np.where(is_in_band)[0]
            out_band = np.where(~is_in_band)[0]
            d2diagv[in_band] **= 2
            d2diagv[out_band] *= 2 * dh
            d2diagv[out_band] -= dh**2
        elif score_function == 'R2S':
            is_in_band = (d2diagv <= dh)
            if circular:
                is_in_band += (d2diagv >= n - dh)
            in_band = np.where(is_in_band)[0]
            out_band = np.where(~is_in_band)[0]
            d2diagv[in_band] **= 2
            d2diagv[out_band] = dh**2

        D2diag_mat = toeplitz(d2diagv)
        prod = np.multiply(X_p, D2diag_mat)
        score = np.sum(prod)

    return score


def spectral_eta_trick3(X, n_iter=50, dh=1, score_function='Huber', return_score=False,
                        do_plot=False, circular=False, norm_laplacian=None,
                        norm_adjacency=None, eigen_solver=None,
                        scale_embedding=False,
                        add_momentum=None,
                        avg_dim=1, avg_scaling=True):
    """
    Performs Spectral Eta-trick Algorithm from
    https://arxiv.org/pdf/1806.00664.pdf
    which calls several instances of the Spectral Ordering baseline (Atkins) to
    try to minimize 1-SUM or Huber-SUM (instead of 2-SUM)
    with the so-called eta-trick.

    Parameters
        ----------
        n_iter : int, default 50
            Number of iterations.

        score_function : string, default pSUM
            Which score we aim to minimize. Either '1SUM', '2SUM', 'Huber', 'R2S'
            (robust 2SUM function from the paper).
            If Huber or R2S, it is computer with the parameter dh provided.
            By design, the algorithm seeks to minimize the Huber loss. However,
            we keep the permutation that yields the best score amongst all, according
            to the score computed with score_function.
            
        dh : int, default 1
            Parameter for the Huber loss minimized.

        circular : boolean, default False
            Whether we wish to find a circular or a linear ordering.

        eigen_solver : string, default 'arpack'
            Solver for the eigenvectors computations. Can be 'arpack', 'amg', or
            'lopbcg'. 'amg' is faster for large sparse matrices but requires the
            pyamg package.

        add_momentum : Nonetype or float, default None.
            gamma parameter in Algorithm... from the paper.
            If gamma > 0, we set eta_{t+1} = gamma * eta_t + (1-gamma) * eta^*,
            where eta^* is the solution at iteration (t).

        avg_dim : int, default 1.
            Number of dimensions to use in the spectral embedding.
            If d = 1, it is the regular eta trick with eta = |pi_i - pi_j|.
            If d > 1, instead we sum |pi^k_i - pi^k_j| over the d first dimensions,
            where pi^k is the permutation that sorts the coordinates of the k-th dimension
            of the spectral embedding (not just the first, which is the Fiedler vector).
        
        avg_scaling : boolean, default True.
            If avg_dim > 1, the previous sum is weighted by the default scaling 1/(1+k)
            if avg_scaling = True.

        return_score : boolean, default False.
            Whether to return the best score (computed with score function) or not.
        
        norm_laplacian : string, default "unnormalized"
            type of normalization of the Laplacian. Can be "unnormalized",
            "random_walk", or "symmetric".

        norm_adjacency : str or bool, default 'coifman'
            If 'coifman', use the normalization of the similarity matrix,
            W = Dinv @ W @ Dinv, to account for non uniform sampling of points on
            a 1d manifold (from Lafon and Coifman's approximation of the Laplace
            Beltrami operator)
            Otherwise, leave the adjacency matrix as it is.
            TODO : also implement the 'sinkhorn' normalization

        scale_embedding : string or boolean, default True
            if scaled is False, the embedding is just the concatenation of the
            eigenvectors of the Laplacian, i.e., all dimensions have the same
            weight.
            if scaled is "CTD", the k-th dimension of the spectral embedding
            (k-th eigen-vector) is re-scaled by 1/sqrt(lambda_k), in relation
            with the commute-time-distance.
            If scaled is True or set to another string than "CTD", then the
            heuristic scaling 1/sqrt(k) is used instead.
        
    """

    (n, n2) = X.shape
    assert(n == n2)

    if n < 3:
        best_perm = np.arange(n)
        if return_score:
            return(best_perm, -1)
        else:
            return(best_perm)

    best_perm = np.arange(n)
    best_score = compute_score(X, score_function=score_function, dh=dh, perm=None)

    if issparse(X):
        if not isinstance(X, coo_matrix):
            X = coo_matrix(X)

        r, c, v = X.row, X.col, X.data
        eta_vec = np.ones(len(v))
        if add_momentum:
            eta_old = np.ones(len(v))

        for it in range(n_iter):

            X_w = X.copy()
            X_w.data /= eta_vec

            default_dim = 8
            if avg_dim > default_dim:
                default_dim = avg_dim + 1

            embedding = spectral_embedding(X_w, norm_laplacian=norm_laplacian,
                                           norm_adjacency=norm_adjacency,
                                           eigen_solver=eigen_solver,
                                           scale_embedding=scale_embedding,
                                           n_components=default_dim)

            new_perm = np.argsort(embedding[:, 0])

            # new_perm = spectral_algo.fit_transform(X_w)
            if np.all(new_perm == best_perm):
                break
            if new_perm[0] > new_perm[-1]:
                embedding = embedding[::-1, :]
                new_perm *= -1
                new_perm += (n-1)

            new_score = compute_score(X, score_function=score_function, dh=dh, perm=new_perm)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            # eta_vec = abs(p_inv[r] - p_inv[c])
            eta_vec = np.zeros(len(r))
            d_ = min(avg_dim, n-1)
            for dim in range(d_):
                # eta_mat = eta_mat + abs(np.tile(embedding[:, dim], n) - np.repeat(embedding[:, dim], n))
                d_perm = np.argsort(embedding[:, dim])
                d_perm = np.argsort(d_perm)
                eta_add = abs(d_perm[r] - d_perm[c])
                if circular:
                    eta_add = np.minimum(eta_add, n - eta_add)

                eta_add = np.maximum(dh, eta_add)

                if avg_scaling:
                    eta_add = eta_add * 1./np.sqrt(1 + dim)

                eta_vec += eta_add
            #     eta_mat = eta_mat + abs(np.tile(d_perm, n) - np.repeat(d_perm, n))
            # eta_vec = np.sum(abs(embedding[r, :d_] - embedding[c, :d_]), axis=1)
            # if circular:
            #     # pass
            #     eta_vec = np.minimum(eta_vec, n - eta_vec)
            # eta_vec = np.maximum(dh, eta_vec)

            if do_plot:
                title = "it %d, score: %1.5e" % (it, new_score)
                plot_mat(X, permut=new_perm, title=title)

    else:
        eta_mat = np.ones((n, n))

        for it in range(n_iter):

            X_w = np.divide(X, eta_mat)

            default_dim = 8
            if avg_dim > default_dim:
                default_dim = avg_dim + 1

            embedding = spectral_embedding(X_w, norm_laplacian=norm_laplacian,
                                           norm_adjacency=norm_adjacency,
                                           eigen_solver=eigen_solver,
                                           scale_embedding=scale_embedding,
                                           n_components=default_dim)

            new_perm = np.argsort(embedding[:, 0])

            # new_perm = spectral_algo.fit_transform(X_w)
            # if new_perm[0] > new_perm[-1]:
            #     embedding = embedding[::-1, :]
            #     new_perm *= -1
            #     new_perm += (n-1)
            # if np.all(new_perm == best_perm):
            #     break

            new_score = compute_score(X, score_function=score_function, dh=dh, perm=new_perm)
            if new_score < best_score:
                best_perm = new_perm

            p_inv = np.argsort(new_perm)

            d_ = min(avg_dim, n-1)
            # eta_vec = np.sum(abs(embedding[r, :d_] - embedding[c, :d_]), axis=1)
            eta_mat = np.identity(n).flatten()
            for dim in range(d_):
                # eta_mat = eta_mat + abs(np.tile(embedding[:, dim], n) - np.repeat(embedding[:, dim], n))
                d_perm = np.argsort(embedding[:, dim])
                d_perm = np.argsort(d_perm)
                eta_add = abs(np.tile(d_perm, n) - np.repeat(d_perm, n))
                if circular:
                    eta_add = np.minimum(eta_add, n - eta_add)

                eta_add = np.maximum(dh, eta_add)

                if avg_scaling:
                    eta_add = eta_add * 1./np.sqrt((1 + dim))
                
                eta_mat = eta_mat + eta_add


            # eta_mat = abs(np.tile(p_inv, n) - np.repeat(p_inv, n))
            # if circular:
            #     # pass
            #     eta_mat = np.minimum(eta_mat, n - eta_mat)
            eta_mat = np.reshape(eta_mat, (n, n))
            # eta_mat = np.maximum(dh, eta_mat)

            if do_plot:
                title = "it %d, score: %1.5e" % (it, new_score)
                plot_mat(X, permut=new_perm, title=title)

    if return_score:
        return(best_perm, best_score)
    else:
        return(best_perm)
    

class SpectralEtaTrick():

    def __init__(self, n_iter=15, dh=1, return_score=False, circular=False,
                 norm_adjacency=None, eigen_solver=None,
                 avg_dim=3, avg_scaling=True):
        self.n_iter = n_iter
        self.dh = dh
        self.return_score = return_score
        self.circular = circular
        self.norm_adjacency = norm_adjacency
        self.eigen_solver = eigen_solver
        self.avg_dim = avg_dim
        self.avg_scaling = avg_scaling

    def fit(self, X):

        ordering_ = spectral_eta_trick3(X, n_iter=self.n_iter, dh=self.dh,
                                       return_score=self.return_score,
                                       circular=self.circular,
                                       norm_adjacency=self.norm_adjacency,
                                       eigen_solver=self.eigen_solver,
                                       avg_dim=self.avg_dim,
                                       avg_scaling=self.avg_scaling)
        self.ordering = ordering_

        return self

    def fit_transform(self, X):

        self.fit(X)
        return self.ordering


if __name__ == '__main__':

    from mdso import SimilarityMatrix, evaluate_ordering
    import matplotlib.pyplot as plt

    for i_exp in range(10):
        np.random.seed(i_exp)

        n = 150
        data_gen = SimilarityMatrix()
        data_gen.gen_matrix(n, type_matrix='CircularBanded', noise_prop=0.1, noise_ampl=5,
                            apply_perm=False)
        X = data_gen.sim_matrix
        # plt.matshow(X)
        # plt.show()
        X = coo_matrix(X)

        pp = spectral_eta_trick(X, do_plot=True, n_iter=30, dh=20, circular=True)

        pp2 = spectral_eta_trick3(X, do_plot=True, n_iter=30, avg_dim=1)

        pp3 = spectral_eta_trick3(X, do_plot=True, dh=20, score_function='Huber', n_iter=100, avg_dim=5, avg_scaling=True)

        pp3 = spectral_eta_trick3(ord_mat, do_plot=True, dh=30, score_function='R2S', n_iter=100, avg_dim=8, avg_scaling=True, eigen_solver='amg')

        pp = spectral_eta_trick(X, do_plot=True, n_iter=50, dh=20, circular=True, eigen_solver='amg')




        kt1 = evaluate_ordering(pp, np.arange(n))
        kt2 = evaluate_ordering(pp2, np.arange(n))
        print("kt1: %2.2f" % (kt1))
        print("kt2: %2.2f" % (kt2))

