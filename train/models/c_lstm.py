#!/usr/bin/env python
# -*-coding=utf-8-*-

import tensorflow as tf
from tensorflow.contrib import rnn

class CLSTM(object):

    def __init__(self, config, embed):
        self.embedding_dim = config["embedding_dim"]
        self.sequence_length = config["sequence_length"]
        self.num_hidden = config["num_hidden"]
        self.num_classes = config["num_classes"]
        self.vocab_sizes = config["vocab_size"]
        self.l2_lambda = config["l2_lambda"]
        self.optimizer = config["optimizer"]
        self.clip_gradients = config["clip_gradients"]
        self.learning_rate = config["learning_rate"]
        self.decay_steps = config["decay_steps"]
        self.decay_rate = config["decay_rate"]

        # conv configuration
        self.filter_size = config["cnn_filter_size"]
        self.pool_size = config["cnn_pool_size"]
        self.num_filters = config["cnn_num_filter"]

        self.input_x = tf.placeholder(dtype = tf.int32, shape = [None, None], name = "input_x")
        self.input_y = tf.placeholder(dtype = tf.int32, shape = [None, None], name = "input_y")

        # todo add dropout
        self.dropout_keep_prob = tf.placeholder(tf.float32, name = "dropout_keep_prob")


        self.global_step = tf.Variable(0, trainable=False, name = "global_step")
        self.epoch_step = tf.Variable(0, trainable=False, name = "epoch_Step")

        self.epoch_increment = tf.assign(self.epoch_step, tf.add(self.epoch_step, tf.constant(1)))

        self.embedding = tf.get_variable(name="char_embeding", initializer=embed)

        self.initializer = tf.random_normal_initializer(stddev = 0.1)

        self.init_weight()

        self.forward()

        self.accuracy = self.get_accuracy()

        self.loss_val  = self.loss()
        self.train_op = self.train()



    def init_weight(self):

         self.w_projection = tf.get_variable(name = "w_projection",
                                             shape = [self.num_hidden, self.num_classes],
                                             initializer = tf.contrib.layers.xavier_initializer())

         self.b_projection = tf.get_variable(name = "b_projection", shape = [self.num_classes])

    def forward(self):
        self.embedded_words = tf.nn.embedding_lookup(self.embedding, self.input_x)
        self.sentence_embeddings_expanded = tf.expand_dims(self.embedded_words, -1)
        # add cnn
        filter = tf.get_variable("filter",
                                 [self.filter_size, self.embedding_dim, 1, self.num_filters],
                                 initializer = self.initializer)

        conv = tf.nn.conv2d(self.sentence_embeddings_expanded,
                            filter,
                            strides=[1, 1, 1, 1],
                            padding="VALID",
                            name="conv")


        b = tf.get_variable("b", [self.num_filters])
        h = tf.nn.relu(tf.nn.bias_add(conv, b), "relu")

        pooled = tf.nn.max_pool(h,
                                ksize=[1, self.pool_size, 1, 1],
                                strides=[1, 1, 1, 1],
                                padding='VALID',
                                name="pool")


        pooled = tf.reduce_mean(pooled, axis = 2)


        lstm_fw_cell = rnn.BasicLSTMCell(self.num_hidden)
        outputs, _ = tf.nn.dynamic_rnn(lstm_fw_cell, pooled, dtype = tf.float32)

        output_rnn = tf.concat(outputs, axis = 2)
        dropout_rnn = tf.nn.dropout(output_rnn, keep_prob=self.dropout_keep_prob)
        self.output_rnn_last = tf.reduce_mean(dropout_rnn, axis = 1)

        with tf.name_scope("output"):
            self.logits = tf.nn.xw_plus_b(self.output_rnn_last, self.w_projection, self.b_projection, name = "logits")
            self.predictions = tf.argmax(self.logits, axis = 1, name = "predictions")
            self.pred_prob = tf.nn.softmax(self.logits, name = "predprob")

    def loss(self):
        with tf.name_scope("loss"):

            losses = tf.nn.softmax_cross_entropy_with_logits(labels = self.input_y, logits = self.logits);

            loss = tf.reduce_mean(losses)
            l2_losses = tf.add_n(
                [tf.nn.l2_loss(v) for v in tf.trainable_variables() if 'bias' not in v.name]) * self.l2_lambda
            loss = loss + l2_losses
            return loss

    def get_accuracy(self):
        with tf.name_scope("accuracy"):
            correct_predictions = tf.equal(self.predictions, tf.cast(tf.argmax(self.input_y, 1), tf.int64))
            accuracy = tf.reduce_mean(tf.cast(correct_predictions, "float"), name = "accuracy")
            return accuracy

    def train(self):
        learning_rate = tf.train.exponential_decay(self.learning_rate,
                                                   self.global_step,
                                                   self.decay_steps,
                                                   self.decay_rate,
                                                   staircase = True)

        train_op = tf.contrib.layers.optimize_loss(self.loss_val,
                                                   global_step = self.global_step,
                                                   learning_rate = learning_rate,
                                                   optimizer = self.optimizer,
                                                   clip_gradients = self.clip_gradients)
        return train_op
