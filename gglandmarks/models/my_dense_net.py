import keras
from keras.applications import VGG16, DenseNet121
from keras.preprocessing.image import ImageDataGenerator, array_to_img, img_to_array, load_img
from keras import Sequential
from keras.layers import Dense, Input, Flatten, Activation, Dropout
from keras.models import Model, load_model
import glob
import os
import numpy as np
from tqdm import tqdm
from .abstract_model import AbstractModel

class MyDenseNet(AbstractModel):
    def __init__(self, input_shape, num_classes, weight_cache_folder=os.getcwd()):
        super().__init__(input_shape, num_classes, weight_cache_folder)

    def create_model(self, input_shape, num_classes):
        base_model = DenseNet121(weights='imagenet', include_top=False)
        for layer in base_model.layers:
            layer.trainable = False

        # Create your own input format (here 3x200x200)
        input = Input(shape=input_shape, name='input')

        # Use the generated model
        base_output = base_model(input)

        # Add the fully-connected layers
        x = Flatten(name='flatten')(base_output)
        # x = Dense(4096, activation='relu', name='fc1')(x)
        x = Dense(num_classes, activation='sigmoid', name='predictions')(x)

        # Create your own model
        model = Model(inputs=input, outputs=x)
        model.compile(loss='categorical_crossentropy',
                      optimizer='rmsprop',
                      metrics=['accuracy'])

        return model
