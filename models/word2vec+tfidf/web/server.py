#!/usr/bin/env python
# coding=utf-8

from flask import Flask, request, render_template, jsonify
app = Flask(__name__)


import re, json, jieba
from gensim import corpora, models
import numpy as np
from sklearn.neighbors import NearestNeighbors

import requests



# 输入是查询歌词文档和 k_input 值
# 输出是最相似的 k_input 篇歌词文档的 id 


### 模型预加载

processed_wrd2vec = '../processed_data/lyrics_all.json_processed_jieba_tfidf_wrd2vec'
processed_data = '../processed_data/lyrics_all.json_processed'
corpus_data = '../processed_data/lyrics.mm'
dictionary_data = '../processed_data/lyrics.dict'
Chinese_Word2Vec_data = '../Chinese_Word2Vec/Word60.model'

# 预建立 k_max 的搜索树，根据用户输入再返回 k_input(< k_max) 篇相似文档
k_max, k_input = 260000, 5

# 载入语料词典
dictionary = corpora.Dictionary.load(dictionary_data)
# 载入语料向量
corpus = corpora.MmCorpus(corpus_data)

w2v = models.Word2Vec.load(Chinese_Word2Vec_data)

# 计算语料的 tfidf
tfidf = models.TfidfModel(corpus)

# 取出语料的 wrd2vec
lyrics_item = []
with open(processed_wrd2vec) as f_read:
    for line in f_read:
        lyrics_item.append(json.loads(line))

# 建立 id 到中文歌词的索引
lyrics_Chinese = {}
with open(processed_data) as f_read:
    for line in f_read:
        temp = json.loads(line)
        lyrics_Chinese[temp['id']] = temp['lyrics']

# 对语料的 wrd2vec 建立搜索树 
lyrics_id, lyrics_vec = [], []
for item in lyrics_item:
    lyrics_id.append(item['id'])
    lyrics_vec.append(item['lyrics_vec'])
nbrs = NearestNeighbors(n_neighbors=k_max, algorithm='brute').fit(lyrics_vec)

@app.route('/query', methods=['POST'])
def query():

    k_input = int(request.form.get('k_input', ''))
    query_lyric = request.form.get('query_lyric', '')

    # 对查询歌词进行清洗和分词
    query_lyric = re.sub(u'[^\u4e00-\u9fa5]', u' ', query_lyric)
    query_lyric = jieba.lcut(query_lyric, cut_all=False)


    # 对查询歌词建立字典
    query_lyric_dict = dictionary.doc2bow(query_lyric)

    # 计算查询歌词的向量
    query_lyric_vec = np.zeros(60)
    for word in tfidf[query_lyric_dict]:
        if dictionary[word[0]] in w2v:
            query_lyric_vec += word[1] * w2v[dictionary[word[0]]]

    # 搜索最相似的 k_max 首歌词
    distance, indices = nbrs.kneighbors(query_lyric_vec)

    # 只返回最相似的 k_input 个 id，id 需要映射一下

    print("+++ Distance max: ", max(distance[0]))
    print("+++ Distance min: ", min(distance[0]))
 
    
    result_ids = []
    for i in range(k_input):
        result_ids.append(lyrics_id[indices[0][i]])

    # id 到中文歌词的映射
    sim_lyrics = []
    for id in result_ids:
        sim_lyrics.append((id, lyrics_Chinese[id]))

    songs_info = []
    # 通过 id 爬取歌曲相关信息
    for songid in result_ids:
        songid = int(songid)
        url = u"http://music.163.com/api/song/detail/?id=%d&ids=%%5B%d%%5D" %(songid,songid)
        response = requests.get(url)
        response = json.loads(response.content.decode('utf8'))['songs'][0]
        song_info = {}
        song_info['artists'] = [artists['name'] for artists in response['artists']]
        song_info['popularity'] = response['popularity']
        song_info['name'] = response['name']
        song_info['picUrl'] = response['album']['picUrl']
        songs_info.append(song_info)

    return jsonify(sim_lyrics=sim_lyrics, songs_info=songs_info)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=2333)