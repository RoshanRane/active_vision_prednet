#!/usr/bin/env python
# coding: utf-8


# import os
# os.environ["CUDA_VISIBLE_DEVICES"]="0,1"


import os, glob, sys
import numpy as np
import pandas as pd
# from matplotlib import pyplot as plt
from PIL import Image as pil_image
from keras import backend as K
from keras_preprocessing.image import get_keras_submodule
import threading

try:
    IteratorType = get_keras_submodule('utils').Sequence
except ImportError:
    IteratorType = object


class myIterator(IteratorType):
    """Base class for image data iterators from keras_preprocessing.image
    modified for our multiple-crop size purpose.

    # Arguments
        n: Integer, total number of samples in the dataset to loop over.
        batch_size: Integer, size of a batch.
        shuffle: Boolean, whether to shuffle the data between epochs.
        seed: Random seeding for data shuffling.
    """

    def __init__(self, n, batch_size, shuffle, seed, grps_boundary=None):
        '''The grps_boundaries is used to define sub-groups within the whole sample group.'''
        self.n = n
        self.batch_size = batch_size   
        
        assert (grps_boundary is None) or (grps_boundary<=self.n), "The index 'grps_boundary' must be less than n (number of samples)"
        self.boundary = grps_boundary
        if(self.boundary is None):
            self.total_batches = self.n//self.batch_size  
        else:
            self.total_batches = ((self.boundary//self.batch_size)  + (self.n - self.boundary)//self.batch_size) 
        
        self.seed = seed
        self.shuffle = shuffle
        self.batch_index = 0
        self.total_batches_seen = 0
        self.lock = threading.Lock()
        self.index_array = None
        self.index_generator = self._flow_index()

    def _set_index_array(self):
        self.index_array = np.arange(self.n)
        if self.shuffle:
            if(self.boundary is None):
                self.index_array = np.random.choice(
                    self.index_array
                    , size=(self.total_batches, self.batch_size)
                    , replace=False
                )
            else:
                # when there are 2 sub-grps shuffle then seperately and then create their batches at indexes
                self.index_array = np.append(
                    np.random.choice(
                        self.index_array[:self.boundary]
                    , size=(self.boundary//self.batch_size, self.batch_size)
                    , replace=False)
                    , np.random.choice(
                        self.index_array[self.boundary:]
                    , size=((self.n - self.boundary)//self.batch_size, self.batch_size)
                    , replace=False)
                , axis = 0)
                np.random.shuffle(self.index_array)
                
#         print(self.index_array)

    def __getitem__(self, idx):
        if idx >= len(self):
            raise ValueError('Asked to retrieve element {idx}, '
                             'but the Sequence '
                             'has length {length}'.format(idx=idx,
                                                          length=len(self)))
        if self.seed is not None:
            np.random.seed(self.seed + self.total_batches_seen)
        self.total_batches_seen += 1
            
        index_array = self.index_array[idx]
        return self._get_batches_of_transformed_samples(index_array)


    def __len__(self):
        return self.total_batches  

    # check if epoch_end has been reached. If yes, reset the iterator and shuffle the data
    def on_epoch_end(self):
        self._set_index_array()

    def reset(self):
        self.batch_index = 0

    def _flow_index(self):
        # Ensure self.batch_index is 0.
        self.reset()
        while 1:
#             print(self.batch_index)
            if self.seed is not None:
                np.random.seed(self.seed + self.total_batches_seen)
            if(self.batch_index == 0):
                self._set_index_array()           
            cur_batch_index = self.batch_index
            # increment batch index for next iter
            if self.batch_index < (self.total_batches -1):
                self.batch_index += 1
            else:
                self.batch_index = 0
                
            self.total_batches_seen += 1
            
            yield self.index_array[cur_batch_index]

    def __iter__(self):
        # Needed if we want to do something like:
        # for x, y in data_gen.flow(...):
        return self

    def __next__(self, *args, **kwargs):
#         return next(self.index_generator)
        return self.next(*args, **kwargs)

    def _get_batches_of_transformed_samples(self, index_array):
        """Gets a batch of transformed samples.
        # Arguments
            index_array: Array of sample indices to include in batch.
        # Returns
            A batch of transformed samples.
        """
        raise NotImplementedError 


# In[66]:


class SmthsmthGenerator(myIterator):    
    '''
    Data generator that creates batched sequences from the smth-smth dataset for input into PredNet.
    info: to generate the data_csv, run the extract_20bn.py script first on the raw smth-smth videos.
    
    Args:
    
        dataframe : Can either be the path to the csv file generated by the extract_20bn.py or 
        be a pandas df of the same csv

        nframes : number of frames to use per video. The policy for selection of these frames can be modified 
        using the nframes_selection_mode parameter
        
        split (optional): The split to use for training. Can be one of 'train', 'val', 'test'.
        
        output_mode (optional): <todo>
        
        nframes_selection_mode (optional): Can be one of "smth-smth-baseline-method" or "dynamic-fps"
        if set as "smth-smth-baseline-method",
        a) For videos < nframes  : replicate the first and last frames.  
        b) For videos > nframes  : sample consecutive 'nframes' such that the sampled videos segments 
        are mostly in the center of the whole video
        if set as "dynamic-fps", <to-do>
        a) For videos < nframes  : Artificially increase fps - Duplicate frames at the begining, end and in between the video to make it equal to nframes.  
        b) For videos > nframes  : Artificially decrease fps - Sample non-consecutive frames from the videos such that the total number of frames equal nframes.
        
        reject_extremes (optional): A tuple which says 
            (reject-videos-with-nframes-lower-than-this, reject-videos-with-nframes-higher-than-this)
        Recommended to set to (10,64) that corresponds to 3 std. dev. for the smth-smth dataset and will
        rejects outliers in the dataset. 
    '''    
    def __init__(self, dataframe
                 , nframes
                 , split = ''
                 , batch_size=8
                 , shuffle=True, seed=None
                 , output_mode='error'
                 , nframes_selection_mode = "smth-smth-baseline-method"
                 , reject_extremes = (None, None)
                 , debug = False
#                  , img_interpolation='nearest'
                 , data_format=K.image_data_format()
                ):
     
        if seed is not None:
            np.random.seed(seed)
        if(isinstance(dataframe,str)):
            df = pd.read_csv(dataframe)    
        else:
            df = dataframe
        
        # select the split subset
        if(split):
            assert split in set(df['split']), "split can be one of ({}) only".format(set(df['split']))
            # select the split subset
            df = df[df['split'] == split]
        
        # select the subset of videos with nframes >= min_nframes and <= max_nframes
        min_nframes, max_nframes = reject_extremes
        if(min_nframes is not None):
            df_subset = df[df.num_of_frames >= min_nframes]
            if(len(df_subset) < 0.7*len(df)) : # if more than 30% rejected then raise a WARNING
                print("WARNING: Rejecting videos less than {}-frames resulted in {:.0f}% of the videos({}) to be discarded.".format(
                    min_nframes, float(len(df_subset))*100/len(df), len(df_subset)))
            df = df_subset
        if(max_nframes is not None): 
            df_subset = df[df.num_of_frames <= max_nframes] 
            if(len(df_subset) < 0.7*len(df)) :  # if more than 30% rejected then raise a WARNING
                print("WARNING: Rejecting videos more than {}-frames resulted in {:.0f}% of the videos({}) to be discarded.".format(
                    max_nframes, float(len(df_subset))*100/len(df), len(df_subset)))
            df = df_subset 
            
        # sort them by the crop group
        self.df = df.sort_values(by=['crop_group']).reset_index(drop=True)
        # required to initialize the parent myIterator class
        self.grp1_boundary = len(self.df[self.df['crop_group']==1])     

        assert output_mode in {'error', 'prediction'}, 'output_mode must be in {error, prediction}'
        self.output_mode = output_mode
        self.batch_size = batch_size
        self.nframes = nframes
        self.shuffle = shuffle
        self.seed = seed
        self.debug = debug
        if(data_format != 'channels_last'): 
            raise NotImplementedError("Only 'channels_last' data_format is currently supported by this class.\
'channels_first' is not supported")
            
        assert nframes_selection_mode in {
            "smth-smth-baseline-method","dynamic-fps"
        }, 'nframes_selection_mode must be one of {"smth-smth-baseline-method", "dynamic-fps"}'
        self.nframes_selection_mode = nframes_selection_mode
        
        super(SmthsmthGenerator, self).__init__(n = len(self.df),
                                        batch_size=batch_size,
                                        shuffle=shuffle, 
                                        seed=seed,
                                        grps_boundary = self.grp1_boundary)
#         if N_seq is not None and len(self.df) > N_seq:  # select a subset of sequences if want to
#             self.df = self.df[:N_seq]        
#         if shuffle:
#             self.df = self.df.sample(frac=1).reset_index(drop=True)

#         self.X = hkl.load(data_file)  # X will be a 4D array of (n_images, nb_cols, nb_rows, nb_channels)        
    
    def _get_batches_of_transformed_samples(self, index_array):
        
        # check which crop size group is expected...preprocessing (1)
        if(all(index_array < self.grp1_boundary)):
            target_im_size = (128,160)
        elif(all(index_array >= self.grp1_boundary)):
            target_im_size = (128,224)
        else:
            raise ValueError("index_array {} contains a mix of both groups.\
They should all be either less than {} or greater than {}".format(
                index_array, self.grp1_boundary, self.grp1_boundary-1))
        
#         # 'channels_first' or 'channels_last'?
#         if(self.data_format == 'channels_last'):
        batch_x = np.empty(((len(index_array),) +  (self.nframes,) + target_im_size + (3,))
                           , dtype=np.float32)
#         else:
#             batch_x = np.empty(((len(index_array),) + (3,) +  (self.nframes,) + self.im_shape)
#                                , dtype=np.float32)       

        for i, idx in enumerate(index_array):
            # read the video dir
            vid_dir = self.df.loc[idx, 'path']
            batch_x[i] = self.fetch_and_preprocess(vid_dir, target_im_size)
        if self.output_mode == 'error':  # model outputs errors, so y should be zeros
            batch_y = np.zeros(self.batch_size, np.float32)
        elif self.output_mode == 'prediction':  # output actual pixels
            batch_y = batch_x
            
        return batch_x, batch_y
    
    def fetch_and_preprocess(self, vid_dir, target_im_size):
        
        frames = sorted(glob.glob(vid_dir+"/*.png"))
        total_frames = len(frames)
        # select exactly 'nframes' from each video dir... preprocessing (4)
        if(self.nframes_selection_mode == "smth-smth-baseline-method"):
            if(total_frames > self.nframes):
                # sample the start frame using a binomial distribution highest probability at the center of the video
                start_frame_idx = np.random.binomial((total_frames - self.nframes), p =0.5) 
                frames_out = frames[start_frame_idx: start_frame_idx + self.nframes]
            elif(total_frames < self.nframes):
                # replicate the first frame and last frame at the ends to match self.nframes
                replicate_cnt_start = (self.nframes - total_frames)//2
                replicate_cnt_end = (self.nframes - (total_frames + replicate_cnt_start))
                frames_out = [frames[0]]*(replicate_cnt_start) + frames + [frames[-1]]*(replicate_cnt_end) 
            else: #total_frames == self.nframes
                frames_out = frames
                
        else:#(self.nframes_selection_mode == "dynamic-fps"):
            if(total_frames > self.nframes):
                # delete frames at regular intervals until exactly nframes are left
                if(self.debug):
                    print("total_frames=",total_frames,"frames_excess=",(total_frames - self.nframes))
                frames_out = frames
                delete_rate = (total_frames//(total_frames - self.nframes))
                deleted = 0
                i = 0 #start by first replicating the 0th frame
                while(len(frames_out) > self.nframes):
                    del_idx = i*delete_rate - deleted
                    if(self.debug):
                        print("removing frame at idx",del_idx)
                    del frames_out[del_idx]
                    i += 1
                    deleted += 1                
            elif(total_frames < self.nframes):               
                # duplicate frames at regular intervals until exactly nframes are left
                if(self.debug):
                    print("total_frames=",total_frames,"frames_shortage=",(self.nframes - total_frames))
                frames_out = frames
                insert_rate = (total_frames//(self.nframes - total_frames))
                inserted = 0
                i = 0 #start by first replicating the 0th frame
                while(len(frames_out) < self.nframes):
                    dup_idx = i*insert_rate + inserted
                    if(self.debug):
                        print("duplicating frame at idx",dup_idx)
                    frames_out.insert(dup_idx, frames[dup_idx])
                    i += 1
                    inserted += 1
            else: #total_frames == self.nframes
                frames_out = frames      
                
#         print(len(frames), len(frames_out), [im.split("/")[-1] for im in im_frames_out])
#         # 'channels_first' or 'channels_last'?
#         if(self.data_format == 'channels_last'):
        X = np.empty(((self.nframes,) + target_im_size + (3,)), dtype=np.float32)
#         else:
#             X = np.empty((((3,) +  (self.nframes,) + self.im_shape)
#                                , dtype=np.float32)
            
        for i,frame in enumerate(frames_out):
            X[i] = self.load_img(frame, target_size=target_im_size)
#             X[i] = img_to_array(load_img(frame, target_size=target_im_size)) 
        X = self.preprocess(X)
    
        return X
    
    
    def load_img(self, img_dir, target_size):
#       _PIL_INTERPOLATION_METHODS = {
#         'nearest': pil_image.NEAREST,
#         'bilinear': pil_image.BILINEAR,
#         'bicubic': pil_image.BICUBIC,
# }
        im = pil_image.open(img_dir)
        w, h = im.size
        w_same_aspect =  int((float(target_size[0])/h)*w)
        im = im.resize((target_size[0], w_same_aspect), pil_image.ANTIALIAS)

        w_crop = (im.size[1] - target_size[1]) // 2
        im = im.crop((0, w_crop, im.size[0], target_size[1]+w_crop))
        im_arr = np.asarray(im, dtype=np.float32)
        im_arr = np.moveaxis(im_arr, 0, 1)
        return im_arr    
    
    
    def preprocess(self, X):
#         self.image_data_generator = ImageDataGenerator(
#                                     featurewise_center=False
#                                      , samplewise_center=False
#                                      , featurewise_std_normalization=False
#                                      , samplewise_std_normalization=False
#                                      , zca_whitening=False
#                                      , zca_epsilon=1e-06
#                                      , rotation_range=0
#                                      , width_shift_range=0.0
#                                      , height_shift_range=0.0
#                                      , brightness_range=None
#                                      , shear_range=0.0
#                                      , zoom_range=0.0
#                                      , channel_shift_range=0.0
#                                      , fill_mode='nearest'
#                                      , cval=0.0
#                                      , horizontal_flip=True
#                                      , vertical_flip=False
#                                      , rescale=1./255
#                                      , preprocessing_function=None
#                                      , data_format='channels_last'
#                                      , validation_split=0.0
#                                      , dtype='float32'
#                                     )
#         X = self.image_data_generator.standardize(X) # standardize to range [0,1]... preprocessing 3
#         params = {'flip_horizontal':True}
#         X = self.image_data_generator.apply_transform(X, params)
        return X / 255

    def next(self):
        """For python 2.x. # Returns  The next batch.
        info : function taken directly from keras_preprocessing.DataFrameIterator class
        """
        # Keeps under lock only the mechanism which advances
        # the indexing of each batch.
        with self.lock:
            index_array = next(self.index_generator)
        # The transformation of images is not under thread lock
        # so it can be done in parallel
        return self._get_batches_of_transformed_samples(index_array)
                      
    def __len__(self):
        return len(self.df)


# In[71]:

if __name__ == '__main__':
    # TEST : runs the generator 10 times and prints out the output dimension of the batches returned
    # GUIDE : how to use the class

    data_csv = "/data/videos/something-something-v2/preprocessed/data.csv"
    val_gen = SmthsmthGenerator(data_csv
                                      , nframes=48
                                      , split = "val"
                                      , batch_size=8
                                      , shuffle=True, seed=42
                                      , nframes_selection_mode = "smth-smth-baseline-method"
                                     )
    print("shape of the next 10 generator outputs:")
    for i in range(10):
        batch,label = next(val_gen)
        print("Batch shape =", batch.shape)
        print("label shape =", label.shape)

    # visualize some frames
    # frames = next(val_gen)[0]
    # f = plt.subplots()
    # for frm in frames:
    #     print("(shape, min, mean, max) =",frm.shape ,np.min(frm), np.mean(frm), np.max(frm))
    #     plt.imshow(frm)
    #     plt.show() 
