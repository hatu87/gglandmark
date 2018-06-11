import numpy as np
from keras.utils import to_categorical
from sklearn.preprocessing import LabelEncoder

class Encoder(object):
    def __init__(self, classes):
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(classes)        

    def encode(self, data):
        Y = self.label_encoder.transform(data)
        Y = to_categorical(Y)

        return Y

    def decode(self, data):        
        idxes = np.argmax(data, axis=1)        
        return self.label_encoder.inverse_transform(idxes)

    @property
    def classes_(self):
        return self.label_encoder.classes_