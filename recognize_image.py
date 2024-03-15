import tensorflow as tf
from PIL import Image
import numpy as np

# Load weights from .npy file
weights_dict = np.load("/home/mpshater/hobby/Show_and_Tell/model/39999.npy", allow_pickle=True).item()

# Initialize layer with 512 input channels
conv5_2_layer = tf.keras.layers.Conv2D(filters=512, kernel_size=3, activation='relu', input_shape=(None, None, 512), name='conv5_2')

# Explicitly build the layer
conv5_2_layer.build(input_shape=(None, None, None, 512))

# Now set the weights
conv5_2_layer.set_weights([weights_dict['conv5_2/conv5_2_W:0'], weights_dict['conv5_2/conv5_2_b:0']])


# Define a simplified model architecture
model = tf.keras.Sequential([
    # ... Other layers (conv1_1, conv2_1, etc.)
    conv5_2_layer,
    # ... Other layers (conv5_3, etc.)
    tf.keras.layers.Flatten(),
    tf.keras.layers.Reshape((4096,)),  # Reshape it to the expected shape for the Dense layer. Adjust the shape as necessary.
    tf.keras.layers.Dense(units=4096, activation='relu', name='fc6'),
    # ... More layers if needed
    tf.keras.layers.LSTM(units=512, name='lstm'),
    # ... More layers if needed
])

# Set weights for individual layers
#model.get_layer(name='conv5_2').set_weights([weights_dict['conv5_2/conv5_2_W:0'], weights_dict['conv5_2/conv5_2_b:0']])
#model.get_layer(name='fc6').set_weights([weights_dict['fc6/fc6_W:0'], weights_dict['fc6/fc6_b:0']])
#model.get_layer(name='lstm').set_weights([weights_dict['lstm/lstm_cell/kernel:0'], weights_dict['lstm/lstm_cell/bias:0']])



# Prepare your image
image_path = "/home/mpshater/images/20230815_065849.jpg"
image = Image.open(image_path)
image = np.array(image.resize((299, 299))) / 255.0  # resizing and normalization
image = np.expand_dims(image, axis=0)  # expand dimensions for batch size

# Prepare the input signature
input_signature = {
    "input_image": tf.convert_to_tensor(image, dtype=tf.float32)
}

# Run inference to generate caption
output_signature = model.signatures["serving_default"](**input_signature)
caption = output_signature["output_caption"].numpy()

# Print the generated caption
print(f"Generated caption: {caption}")
