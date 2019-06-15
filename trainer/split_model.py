import trainer.constants as cst

from tensorflow.keras.layers import concatenate, LSTM, Conv1D, Flatten, TimeDistributed, Input, Dense, MaxPooling1D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
import tensorflow.keras.backend as K
import tensorflow as tf

from trainer.data_pipeline import load_scaling_factors


def mae_remaining_cycles(y_true, y_pred):
    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.dtypes.cast(y_true, y_pred.dtype)
    diff = tf.math.abs(y_true - y_pred)
    return K.mean(diff, axis=0)[1] * 2159.0  # TODO: hard coded for now!


def mae_current_cycle(y_true, y_pred):
    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.dtypes.cast(y_true, y_pred.dtype)
    diff = tf.math.abs(y_true - y_pred)
    return K.mean(diff, axis=0)[0] * 2159.0  # TODO: hard coded for now!


def get_mape_current_cycle():
    scaling_factors = load_scaling_factors()
    
    def mape_current_cycle(y_true, y_pred):
        """Copied from tf.keras.losses.mean_absolute_percentage_error and changed the axis to 0.
        This calculates the mean over the two different outputs of the model."""
        y_pred = tf.convert_to_tensor(y_pred)
        y_true = tf.dtypes.cast(y_true, y_pred.dtype)
        diff = tf.math.abs(
            (y_true - y_pred) / K.clip(tf.math.abs(y_true), 1 / scaling_factors[cst.REMAINING_CYCLES_NAME], None))
        return 100. * K.mean(diff, axis=0)[0]
    return mape_current_cycle


def get_mape_remaining_cycles():
    scaling_factors = load_scaling_factors()
    
    def mape_remaining_cycles(y_true, y_pred):
        """Copied from tf.keras.losses.mean_absolute_percentage_error and changed the axis to 0.
        This calculates the mean over the two different outputs of the model."""
        y_pred = tf.convert_to_tensor(y_pred)
        y_true = tf.dtypes.cast(y_true, y_pred.dtype)
        diff = tf.math.abs(
            (y_true - y_pred) / K.clip(tf.math.abs(y_true), 1 / scaling_factors[cst.REMAINING_CYCLES_NAME], None))
        return 100. * K.mean(diff, axis=0)[1]
    return mape_remaining_cycles


def get_log_acc_ratio_current_cycle():
    scaling_factors = load_scaling_factors()
    
    def log_acc_ratio_current_cycle(y_true, y_pred):
        """Copied from tf.keras.losses.mean_absolute_percentage_error and changed the axis to 0.
        This calculates the mean over the two different outputs of the model."""
        y_pred = tf.convert_to_tensor(y_pred)
        y_true = tf.dtypes.cast(y_true, y_pred.dtype)
        y_true_clipped = K.clip(tf.math.abs(y_true), 1 / scaling_factors[cst.REMAINING_CYCLES_NAME], None)
        log_acc_ratio = tf.math.log((tf.math.abs(y_pred) / y_true_clipped) + 1)
        return K.mean(log_acc_ratio, axis=0)[0]
    return log_acc_ratio_current_cycle


def get_log_acc_ratio_remaining_cycles():
    scaling_factors = load_scaling_factors()
    
    def log_acc_ratio_remaining_cycles(y_true, y_pred):
        """Copied from tf.keras.losses.mean_absolute_percentage_error and changed the axis to 0.
        This calculates the mean over the two different outputs of the model."""
        y_pred = tf.convert_to_tensor(y_pred)
        y_true = tf.dtypes.cast(y_true, y_pred.dtype)
        y_true_clipped = K.clip(tf.math.abs(y_true), 1 / scaling_factors[cst.REMAINING_CYCLES_NAME], None)
        log_acc_ratio = tf.math.log((tf.math.abs(y_pred) / y_true_clipped) + 1)
        return K.mean(log_acc_ratio, axis=0)[1]
    return log_acc_ratio_remaining_cycles


def get_log_acc_ratio_loss():
    scaling_factors = load_scaling_factors()
    
    def log_acc_ratio_loss(y_true, y_pred):
        """Copied from tf.keras.losses.mean_absolute_percentage_error and changed the axis to 0.
        This calculates the mean over the two different outputs of the model."""
        y_pred = tf.convert_to_tensor(y_pred)
        y_true = tf.dtypes.cast(y_true, y_pred.dtype)
        y_true_clipped = K.clip(tf.math.abs(y_true), 1 / scaling_factors[cst.REMAINING_CYCLES_NAME], None)
        log_acc_ratio = tf.math.log((tf.math.abs(y_pred) / y_true_clipped) + 1)
        return tf.math.reduce_mean(log_acc_ratio)
    return log_acc_ratio_loss


def create_keras_model(window_size, loss, optimizer):
    """Creates the Keras model.

    Args:
    window_size: [...]
    """
    # define Inputs
    qdlin_in = Input(shape=(window_size, cst.STEPS, cst.INPUT_DIM), name=cst.QDLIN_NAME)
    tdlin_in = Input(shape=(window_size, cst.STEPS, cst.INPUT_DIM), name=cst.TDLIN_NAME)
    ir_in = Input(shape=(window_size, cst.INPUT_DIM), name=cst.INTERNAL_RESISTANCE_NAME)
    dt_in = Input(shape=(window_size, cst.INPUT_DIM), name=cst.DISCHARGE_TIME_NAME)
    qd_in = Input(shape=(window_size, cst.INPUT_DIM), name=cst.QD_NAME)
    
    # combine all data from detail level
    detail_concat = concatenate([qdlin_in, tdlin_in], axis=3, name='detail_concat')

    # define CNN
    cnn_out = TimeDistributed(Conv1D(filters=16, kernel_size=5, activation='relu'), name='convolution')(detail_concat)
    # Add some maxpools to reduce output size
    cnn_maxpool = TimeDistributed(MaxPooling1D(), name='conv_pool')(cnn_out)
    cnn_out2 = TimeDistributed(Conv1D(filters=16, kernel_size=5, activation='relu'), name='conv2')(cnn_maxpool)
    cnn_maxpool2 = TimeDistributed(MaxPooling1D(), name='pool2')(cnn_out2)
    cnn_flat = TimeDistributed(Flatten(), name='convolution_flat')(cnn_maxpool2)

    # combine CNN output with all data from summary level
    all_concat = concatenate([cnn_flat, ir_in, dt_in, qd_in], axis=2, name='all_concat')

    # define LSTM
    lstm_out = LSTM(64, activation='relu', name='recurrent')(all_concat)
    hidden_dense = Dense(32, name='hidden', activation='relu')(lstm_out)
    main_output = Dense(2, name='output')(hidden_dense)  # Try different activations that are not negative

    model = Model(inputs=[qdlin_in, tdlin_in, ir_in, dt_in, qd_in], outputs=[main_output])
    
    metrics_list = [mae_current_cycle, mae_remaining_cycles]
    
    model.compile(loss=loss, optimizer=Adam(clipnorm=1.), metrics=metrics_list)  # Try lower learning rate

    return model