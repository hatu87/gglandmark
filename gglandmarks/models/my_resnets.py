import tensorflow as tf
from .tf_base_model import TFBaseModel, _optimize, _input_layer, _loss
import os
from gglandmarks.datasets import GoogleLandmarkDataset
import datetime


def _conv_layer(input, kernel_size, filters, padding='same', strides=(1, 1), activation=tf.nn.relu, batch_norm=True, name='conv'):
    with tf.variable_scope(name):
        conv_input = input
        conv = tf.layers.Conv2D(
            filters=filters,
            kernel_size=kernel_size,
            padding=padding,
            strides=strides,
            activation=None,
            use_bias=False,
            kernel_initializer=tf.keras.initializers.he_normal()
        )
        conv_out = conv(conv_input)

        if batch_norm:
            batch_out = tf.layers.batch_normalization(
                conv_out,
                axis=3,
                scale=False,
                name='batch_normalization')
        else:
            batch_out = conv_out

        if activation is not None:
            output = activation(batch_out)
        else:
            output = batch_out

        weights = conv.trainable_weights

        # tf.summary.histogram('weights', weights)
        # # tf.summary.histogram('biases', bias)
        # tf.summary.histogram(
        #     'sparsity/conv', tf.nn.zero_fraction(conv_out))
        # tf.summary.histogram('batch_output', batch_out)
        # tf.summary.histogram('output', output)
        # tf.summary.histogram(
        #     'sparsity/output', tf.nn.zero_fraction(output))

        return output


def _identity_block_layer(input, f, filters, name):
    """[summary]

    Arguments:
        input [tensor] -- input tensor
        f [integer] -- channel out size of the middle conv layer
        filters [python list of integers] -- the number of filters of each conv layer
        name [string] -- name of layer

    Returns:
        [tensor] -- output layer
    """

    with tf.variable_scope(name):
        X = input

        X = _conv_layer(input=X,
                        kernel_size=(1, 1),
                        filters=filters[0],
                        strides=(1, 1),
                        padding='valid',
                        activation=tf.nn.relu,
                        name='res2a')

        X = _conv_layer(input=X,
                        kernel_size=(f, f),
                        filters=filters[1],
                        strides=(1, 1),
                        padding='same',
                        activation=tf.nn.relu,
                        name='res2b')

        X = _conv_layer(input=X,
                        kernel_size=(1, 1),
                        filters=filters[2],
                        strides=(1, 1),
                        padding='valid',
                        activation=None,
                        name='res2c')

        X = tf.add(input, X)
        X = tf.nn.relu(X)

        return X


def _convolution_block_layer(input, f, filters, s, name):
    """[summary]

    Arguments:
        input [tensor] -- input tensor
        f [integer] -- channel out size of the middle conv layer
        filters [python list of integers] -- the number of filters of each conv layer
        s [integer] -- stride of first conv layer to use
        name [string] -- name of layer

    Returns:
        [tensor] -- output layer
    """

    with tf.variable_scope(name):
        X = input

        X = _conv_layer(input=X,
                        kernel_size=(1, 1),
                        filters=filters[0],
                        strides=(s, s),
                        padding='valid',
                        activation=tf.nn.relu,
                        name='res2a')

        X = _conv_layer(input=X,
                        kernel_size=(f, f),
                        filters=filters[1],
                        strides=(1, 1),
                        padding='same',
                        activation=tf.nn.relu,
                        name='res2b')

        X = _conv_layer(input=X,
                        kernel_size=(1, 1),
                        filters=filters[2],
                        strides=(1, 1),
                        padding='valid',
                        activation=None,
                        name='res2c')

        shortcut = _conv_layer(input=input,
                               kernel_size=(1, 1),
                               filters=filters[2],
                               strides=(s, s),
                               padding='valid',
                               activation=None,
                               name='shortcut')

        X = tf.add(X, shortcut)
        X = tf.nn.relu(X)

        return X


def fc_layer(input, channels_out, activation=None, name='fc'):
    with tf.variable_scope(name):
        # if activation == tf.nn.relu:
        he_initializer = tf.keras.initializers.he_normal()

        layer = tf.layers.Dense(channels_out, use_bias=True, activation=activation,
                                kernel_initializer=he_initializer, bias_initializer=tf.zeros_initializer)
        value = layer(input)

        weights, bias = layer.trainable_weights

        tf.summary.histogram('weights', weights)
        tf.summary.histogram('biases', bias)
        tf.summary.histogram('activation', value)
        tf.summary.histogram('sparsity', tf.nn.zero_fraction(value))
        return value


def _inference(features, params):
    X = _input_layer(features)

    X = tf.keras.layers.ZeroPadding2D(padding=(3, 3))(X)

    # Stage 1
    X = _conv_layer(input=X,
                    filters=64,
                    strides=(2, 2),
                    kernel_size=(7, 7),
                    padding='valid',
                    activation=tf.nn.relu)
    X = tf.layers.max_pooling2d(inputs=X, pool_size=(3, 3), strides=(2, 2))

    # Stage 2
    filters = [
        [],
        [],
        [64, 64, 256],
        [128, 128, 512],
        [256, 256, 1024],
        [512, 512, 2048],
    ]
    strides = [0, 0, 1, 2, 2, 2]
    kernel_sizes = [0, 0, 3, 3, 3, 3]
    num_identity_blocks = params['num_identity_blocks']

    for stage in range(2, 6):
        with tf.variable_scope('stage-' + str(stage)):
            X = _convolution_block_layer(input=X,
                                         f=kernel_sizes[stage],
                                         filters=filters[stage],
                                         s=strides[stage],
                                         name='stage-{}-0'.format(stage))
            for i in range(num_identity_blocks[stage]):
                X = _identity_block_layer(input=X,
                                          f=kernel_sizes[stage],
                                          filters=filters[stage],
                                          name='stage-{}-{}'.format(stage, str(i + 1)))

    X = tf.layers.average_pooling2d(inputs=X,
                                    pool_size=(2, 2),
                                    strides=(2, 2))

    X = tf.layers.flatten(inputs=X)

    denses_count = params['denses_count'] if 'denses_count' in params else 0
    for i in range(denses_count):
        X = fc_layer(input=X,
                     channels_out=1024,
                     activation=tf.nn.relu,
                     name='fc_layer-' + str(i))

    Y_hat = fc_layer(input=X,
                     channels_out=params['num_classes'],
                     activation=None,
                     name='logits')

    return Y_hat


def _model_fn(features, labels, mode, params):
    """[summary]

    Arguments:
        features {[type]} -- [description]
        labels {[type]} -- [description]
        mode {[type]} -- [description]
        params {[type]} -- [description]

    Returns:
        [type] -- [description]
    """

    logits = _inference(features, params)
    loss = _loss(labels, logits)

    predicted_classes = tf.argmax(logits, 1)

    # prediction
    predictions = {
        'class_ids': predicted_classes[:, tf.newaxis],
        'probabilities': tf.nn.softmax(logits),
        'logits': logits
    }

    if mode == tf.estimator.ModeKeys.PREDICT:
        return tf.estimator.EstimatorSpec(mode, predictions=predictions)

    accuracy = tf.metrics.accuracy(labels=labels,
                                   predictions=predicted_classes,
                                   name='acc_op')

    metrics = {'accuracy': accuracy}
    tf.summary.scalar('accuracy', accuracy[1])

    if mode == tf.estimator.ModeKeys.EVAL:
        return tf.estimator.EstimatorSpec(mode, eval_metric_ops=metrics)

    # train
    train_op = _optimize(loss, params)

    if mode == tf.estimator.ModeKeys.TRAIN:
        return tf.estimator.EstimatorSpec(mode, loss=loss, train_op=train_op)

    return tf.estimator.EstimatorSpec(
        mode,
        loss=loss,
        eval_metric_ops=metrics,
        predictions=predictions,
        train_op=train_op
    )


class MyResNets(TFBaseModel):
    def __init__(self, model_dir):
        super().__init__(name='my-resnets', model_dir=model_dir, model_fn=_model_fn)

    @staticmethod
    def finetune(data_path, image_original_size, model_dir):
        learning_rates = [0.00001]
        batch_size = 32
        target_size = 128
        num_identity_blocks = [
            [0, 0, 2, 3, 7, 2]
        ]
        for learning_rate in learning_rates:
            dataset = GoogleLandmarkDataset(
                data_path, (image_original_size[0], image_original_size[1]), images_count_min=500)
            print(dataset.train_df.shape)
            print(dataset.num_classes)

            model_params = {
                'num_classes': dataset.num_classes,
                'learning_rate': learning_rate,
                'num_identity_blocks': num_identity_blocks[0],
                'denses_count': 0,
                'decay_steps': None,
                'optimizer': 'rmsprop'
            }

            model = MyResNets(model_dir=model_dir)
            model.build(dataset=dataset,
                        batch_size=batch_size,
                        target_size=(target_size, target_size),
                        params=model_params)

            logname = 'lrd={}-cls={}-nib={}-i={}-b={}-dc={}-ds={}-o={}'.format(learning_rate,
                                                                               dataset.num_classes,
                                                                               model_params['num_identity_blocks'],
                                                                               target_size,
                                                                               batch_size,
                                                                               model_params['denses_count'],
                                                                               model_params['decay_steps'],
                                                                               model_params['optimizer']).replace('[', '(').replace(']', ')')

            total_losses, total_accuracies = model.fit(train_iter=model.train_iter,
                                                       eval_iter=model.eval_iter,
                                                       logname=logname)

            print('accuracy:{} - losses: {}'.format(total_accuracies, total_losses))
