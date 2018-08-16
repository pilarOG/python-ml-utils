# -*- coding: utf-8 -*-

# Most of this code belongs to:
# https://deeplearningcourses.com/c/cluster-analysis-unsupervised-machine-learning-python
# https://www.udemy.com/cluster-analysis-unsupervised-machine-learning-python

############################################################################
# The soft k-means algorithm is commented through out the code to understand the lectures. I'll try to add a read me with the formulas to have the full explanation!
#
# For other explanations:
# http://rosalind.info/problems/ba8d/
# https://blog.tshw.de/wp-content/uploads/2009/03/soft-clustering.pdf
#
# Symbols:
#
# D = dimensionality, number of features
# N = number of samples
# X = N x D matrix, input data to the algorithm
# K = number of clusters
# M = K x D matrix of means or cluster centers
# R = K x N responsability matrix, how much each sample belongs to each k
# beta = stiffnes parameter, or amount of flexibility in soft assignment
# d = distance
#
############################################################################


from __future__ import print_function, division
from future.utils import iteritems
from builtins import range, input
# Note: you may need to update your version of future
# sudo pip install -U future
from sklearn.decomposition import PCA
from gensim.models import Word2Vec
import numpy as np
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
import codecs
import unicodedata
import gensim
from sklearn.metrics import pairwise_distances_argmin

# Some spanish stopwords (with some misspellings too)
stopwords = [u'del', u'la', u'de', u'y', u'en', u'un', u'el', u'la', u'un', u'una', u'los', u't', u'd',
         u'ls', u'las', u'unos', u'unas', u'uns', u'del', u'dl', u'al', u'la', u'el', u'le', u'p', u'hay',
         u'esta', u'lo', u'fue', u'es', u'quien', u'su', u'sus', u'mas', u'durante', u'hasta', u'estos',
         u'las', u'los', u'y', u'con', u'de', u'para', u'por', u'al', u'a', u'ha', u'luego', u'estar',
         u'respectivamente', u'asimismo', u'l', u'cuando', u'les', u'montt',
         u'son', u'ese', u'era', u'eran', u'ser', u'm', u'e', u'g', u'esos', u'eso', u'asi', u'esa', u'esto',
         u'desde', u'una', u'un', u'o', u'en', u'me', u'y', u'se', u'que', u'como', u'porque', u'este', u'']

# Function to very naive tokenization of words for Spanish
# Input is a string/sentence, output a list ok tokens
def my_tokenizer(s):
    # Replace symbols and vowels with diacritics (and other leftovers from the newspaper website)
    s = s.lower().replace('-', '').replace(')', '').replace('(', '').replace('\'', '').replace('\"', '').replace('|', '').replace(';', '').replace(':', '').replace(u'á', 'a')
    s = s.replace(u'é', 'e').replace(u'í', 'i').replace(u'ó', 'o').replace(u'ú', 'u').replace(u'ñ', 'n').replace(u'\u201d', '').replace(u'\u201c', '').replace(u'\xa0','')
    # lemmatization does not work very well for Spanish so we will use normal tokens
    tokens = []
    tokens = [t for t in s.split(' ')] # tokenization just at blank space
    tokens = [t for t in tokens if t not in stopwords] # remove stopwords
    tokens = [t for t in tokens if not any(c.isdigit() for c in t)] # remove digits
    return tokens

def plot_iterative_cost(y):
    plt.figure(figsize=(15, 15))
    axes = plt.gca()
    axes.set_xlim(1, len(y))
    plt.plot(y)
    plt.plot(y.index(min(y)),min(y), marker='o')
    plt.annotate(s='k='+str(y.index(min(y))),xy=(y.index(min(y)),min(y)),xytext=(y.index(min(y)),min(y)))
    plt.title("Costs")
    plt.savefig("cost.png")
    plt.show()

def takeClosest(num,collection):
    return min(collection,key=lambda x:abs(x-num))

def plot_reduced_data(means, assigned_clusters, kmeans_k, Z, word_index, plot_name='test.png'):
    plt.figure(figsize=(15, 15))
    # We will only annotate words that are closest to the centroids
    labels = {}
    for mean in range(0, means.shape[0]):
        row = list(means[mean,:])
        row2 = []
        centroid = (sum(row))/len(row) # calculate centroid of the cluster
        # calculate which is the closest data point in the cluster to the centroid
        [row2.append(row[i]) for i in range(0, len(row)) if assigned_clusters[i] == mean]
        if row2:
            closest = takeClosest(centroid, row2)
            i = row.index(closest)
            label = word_index[i]
            labels[label] = Z[i,:][0],Z[i,:][1]
    for label in labels:
        plt.annotate(label, labels[label], horizontalalignment='center', verticalalignment='center', size=10, color='red')

    # Create scatter plots of each cluster. We will use the coordinates given by Z for each datapoint,
    # (because we can't plot something that is not 2-D), but the mark of the datapoint will correspond
    # to the cluster it was assigned. So we will be able to see both representations.
    scatters = []
    cluster_names = []
    for k in range(0, kmeans_k):
        cluster_names.append('Cluster '+str(k))
        x, y = [], []
        for i in range(0, Z.shape[0]):
            if assigned_clusters[i] == k:
                x.append(Z[i,0])
                y.append(Z[i,1])
        scat = plt.scatter(x,y,c=np.random.random((kmeans_k,)),marker=np.random.choice(['o', '*', 'h','d', 'v', '^', '<', '>']))
        scatters.append(scat)
    plt.legend(scatters,cluster_names, scatterpoints=1, loc='lower left', ncol=8,fontsize=6)
    plt.savefig(plot_name)
    plt.show()

# Function to measure distance
def get_distance(u, v):
    diff = u - v
    return diff.dot(diff)

# Function to calculate cost
def cost(X, R, M):
    cost = 0
    for k in range(len(M)):
        diff = X - M[k]
        sq_distances = (diff * diff).sum(axis=1)
        cost += (R[:,k] * sq_distances).sum()
    return cost

# Main algorithm, soft k-means
def soft_k_means(X, K, index_word_map, prob_vector, max_iter=20, beta=1.0):
    N, D = X.shape
    M = np.zeros((K, D))
    R = np.zeros((N, K))
    exponents = np.empty((N, K))

    # initialize M to random
    for k in range(K):
        M[k] = X[np.random.choice(N, p=prob_vector)]

    costs = np.zeros(max_iter)
    for i in range(max_iter):
        # step 1: determine assignments / resposibilities
        # is this inefficient?
        for k in range(K):
            for n in range(N):
                # R[n,k] = np.exp(-beta*d(M[k], X[n])) / np.sum( np.exp(-beta*d(M[j], X[n])) for j in range(K) )
                exponents[n,k] = np.exp(-beta*get_distance(M[k], X[n]))

        R = exponents / exponents.sum(axis=1, keepdims=True)

        # step 2: recalculate means
        for k in range(K):
            M[k] = R[:,k].dot(X) / R[:,k].sum()

        costs[i] = cost(X, R, M)
        if i > 0:
            if np.abs(costs[i] - costs[i-1]) < 10e-5:
                break
        print ('cost', costs[i])

    # print out the clusters
    hard_responsibilities = np.argmax(R, axis=1) # is an N-size array of cluster identities
    # let's "reverse" the order so it's cluster identity -> word index
    cluster2word = {}
    for i in range(len(hard_responsibilities)):
      word = index_word_map[i]
      cluster = hard_responsibilities[i]
      if cluster not in cluster2word:
        cluster2word[cluster] = []
      cluster2word[cluster].append(word)

    # print out the words grouped by cluster
    for cluster, wordlist in cluster2word.items():
      print("cluster", cluster, "->", wordlist)

    return M, R, costs, X, hard_responsibilities


########## MAIN #################
# 300-6-3-40-30
def main(embedding_vector_size=300,
         embedding_window_size=6,
         embedding_min_count=3,
         tsne_perplexity=40,
         kmeans_k=30,
         show_cost_plot=False,
         plot_name='test.png',
         show_cluster_plot=True,
         reducer='tsne'):

    # Load the data and split at some naive sentence boundaries
    # I'm doing this to have more documents given that I could find just 30 to 40 news of uneven lengths
    cleaned_docs = []
    docs = codecs.open('noticias-emol.txt', encoding='utf-8').read().split('\n')
    [cleaned_docs.append(do) for do in docs if 'http' not in do and do] # This is an extra step to take out the links in the data
    docs = [line.rstrip() for line in '\n'.join(cleaned_docs).replace(',', '\n').replace('.', '\n').replace('\"', '\n').split('\n')]
    print ('Number of document fragments: '+str(len(docs)))

    # We tokenize each word in the fragments, turning each into a list of tokens
    all_tokens = []
    [all_tokens.append(my_tokenizer(doc)) for doc in docs]

    # Word embedding training: a list of list is feed into the model
    model = Word2Vec(size=embedding_vector_size, window=embedding_window_size, min_count=embedding_min_count) # Hyperparameters to experiment with
    model.build_vocab(all_tokens)
    model.train(all_tokens, total_examples=model.corpus_count, epochs=model.iter)
    word_vectors = model.wv

    # Given the trained embeddings we can already get some interesting results. Here we are searching
    # in the model some specific relevant word given the topic and the function allows us to get back the
    # other words that are closest to the given word. In the Readme there is a deeper analysis of this.

    # print(word_vectors.similar_by_word("hombre"))
    # print(word_vectors.similar_by_word("mujer"))
    # print(word_vectors.similar_by_word("violencia"))
    # print(word_vectors.similar_by_word("genero"))
    # print(word_vectors.similar_by_word("asesino"))
    # print(word_vectors.similar_by_word("victima"))
    # print(word_vectors.similar_by_word("ministra"))
    # print(word_vectors.similar_by_word("fiscalia"))
    # print(word_vectors.similar_by_word("feminazi"))
    # print(word_vectors.most_similar(positive=["asesino"])) # aparece menos de 7 veces
    # print(word_vectors.most_similar(negative=["asesino"]))

    # Given the trained we will build a matrix of similarity between all words,
    # of sixe N_words X N_words, as we want to cluster similar words.
    # To build it using gensim directly I used this code, you can also check the documentation
    # for more detail
    # https://groups.google.com/forum/#!topic/gensim/gfOuXGzvsA8
    # https://radimrehurek.com/gensim/models/keyedvectors.html
    # TODO: give more detail on this code
    similarity_matrix = []
    index = gensim.similarities.MatrixSimilarity(gensim.matutils.Dense2Corpus(model.wv.syn0.T))
    [similarity_matrix.append(sims) for sims in index]
    similarity_array = np.array(similarity_matrix)
    word_index = model.wv.index2word

    # In parallel I will use the frequencies to build a vector of the probability of each word using the data
    # We use this vector to initialize the means (M) in the algorithm, hoping it is informative
    frequency = {}
    rare_words = []
    for token in word_index: # Now we want each token independent of their document
        if token not in word_vectors.vocab: rare_words.append(token) #TODO: print this or do something with it
        else:
            if token not in frequency: frequency[token] = 1
            else: frequency[token] += 1
    probs = []
    total_count = sum(frequency.values())
    [probs.append(float(frequency[token])/float(total_count)) for token in word_index]

    # Finally, we will reduce the dimensionality of the embeddings with t-SNE
    # For further information read: http://www.jmlr.org/papers/volume9/vandermaaten08a/vandermaaten08a.pdf
    # To check the function parameters: http://scikit-learn.org/stable/modules/generated/sklearn.manifold.TSNE.html
    # https://distill.pub/2016/misread-tsne/

    if reducer == 'tsne':
        reducer = TSNE(perplexity=tsne_perplexity, random_state=0) # Hyperparameter to tune
        Z = reducer.fit_transform(similarity_array)
    elif reducer == 'pca':
        pca = PCA(n_components=2)
        Z = pca.fit_transform((similarity_array))

    # Run Kmeans TODO: we need to try different Ks and plot that against the cost
    if show_cost_plot==False:
        means, _, costs, _, hard = soft_k_means(similarity_array, kmeans_k, word_index, prob_vector=probs)
        if show_cluster_plot==True:
            plot_reduced_data(means, hard, kmeans_k, Z, word_index,plot_name=plot_name)
        return costs

    else:
        iteration_costs = []
        for k in range(5, kmeans_k, 5):
            print ('k', k)
            means, _, costs, _, hard = soft_k_means(similarity_array, kmeans_k, word_index, prob_vector=probs)
            iteration_costs.append(costs[-1])
        plot_iterative_cost(iteration_costs)

# Run. Defined main to run hypermamter tuning

main(show_cost_plot=True, kmeans_k=50)
'''
outf = open('results_perplexity.txt', 'w')
# For example, tune embedding_vector_size
for tuning in range(20,120,20):
    n_cost = main(tsne_perplexity=tuning, plot_name='test_tsne_'+str(tuning)+'.png')
    outf.writelines(str(tuning)+'\t'+str(n_cost[-1])+'\n')
outf.close()
'''